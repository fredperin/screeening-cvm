"""
Comparador de versões (sem IA): confere os dados recém-gerados (site/dados) contra os da execução anterior,
para que nenhuma alteração do pipeline (otimização de consultas, mudança de fonte, correção) piore o que o
site mostra sem que ninguém perceba.

- Problema: arquivo ou série que sumiu, série que ficou vazia, última data que andou para trás, histórico
  encurtado (início mais de 60 dias depois), buracos no meio da série, empresas ou itens que saíram da lista.
- Revisão da fonte: valor antigo que mudou (PIB, Comex, crédito e balanços são revisados pelas próprias
  fontes). Não é erro: fica registrado para conferência.

Problemas ficam visíveis por DIAS_ALERTA dias (o monitor acusa), mesmo que a execução seguinte já os tome
como nova referência. Saída: data/pipeline/comparacao.json e site/dados/comparacao.json.
Uso: py -m pipeline.comparar PASTA_DOS_DADOS_ANTERIORES
"""

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from pipeline import DIR_DADOS_SITE, DIR_INTERMEDIARIO

ARQ = DIR_INTERMEDIARIO / "comparacao.json"
DIAS_ALERTA = 3
FUSO_BR = timezone(timedelta(hours=-3))  # o GitHub Actions roda em UTC: horários sempre em Brasília
# arquivos de controle, que mudam por natureza a cada execução
NAO_COMPARAR = {"observacoes.json", "saude.json", "status.json", "validacao.json", "comparacao.json", "atualizacoes.json"}
# listas que andam com o tempo (agenda: eventos passados saem; notícias e eventos: janela dos últimos dias)
ROLANTES = ("agenda", "noticias", "eventos_recentes")
# Campos retirados de propósito (decisão registrada): a falta deles não é problema. data = quando foi retirado
REMOVIDOS_DE_PROPOSITO = {
    "demonstracoes_sec": "2026-10-21",  # demonstrações "como divulgadas" da SEC: a página de cada empresa americana ficou só com Negócio e Documentos
}
IGNORAR_CHAVES = {"falhas", "avisos", "abertas", "resolvidas_agora", "descartados"}
EIXOS = ("datas", "periodos", "anos", "trimestres")
MAX_ADIANTO_INICIO = 60    # dias que o início de uma série pode andar (janelas móveis: últimos 12 meses, 1 ano etc.)
TOLERANCIA = 1e-6          # diferença relativa abaixo disso é arredondamento


def _data(x):
    """'2026-09-01', '2026-09', '2026-Q3', '2026T3', '2026' -> date (para comparar posições na série)."""
    s = str(x)
    try:
        if len(s) >= 10:
            return date.fromisoformat(s[:10])
        if "Q" in s or "T" in s:
            ano, tri = s.replace("T", "Q").split("Q")
            return date(int(ano.strip("-")), int(tri) * 3, 1)
        if len(s) == 7:
            return date(int(s[:4]), int(s[5:7]), 1)
        return date(int(s[:4]), 12, 31)
    except (ValueError, IndexError):
        return None


def _numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _tem_historico(v, nivel=0):
    """Se o bloco guarda histórico (lista com 5+ itens em algum nível). Um retrato do dia que some
    (ex.: cotação de um papel sem negócio no pregão) não é perda de dado."""
    if isinstance(v, list):
        return len(v) >= 5
    if isinstance(v, dict) and nivel < 3:
        return any(_tem_historico(x, nivel + 1) for x in v.values())
    return False


class Comparacao:
    def __init__(self):
        self.problemas, self.revisoes, self.series, self.arquivos = [], {}, 0, 0

    def problema(self, arquivo, caminho, detalhe):
        self.problemas.append({"arquivo": arquivo, "caminho": caminho, "detalhe": detalhe})

    def revisao(self, arquivo, caminho, n, exemplo):
        r = self.revisoes.setdefault(arquivo, {"series": 0, "pontos": 0, "exemplo": None})
        r["series"] += 1
        r["pontos"] += n
        r["exemplo"] = r["exemplo"] or f"{caminho}: {exemplo}"

    # ---------- séries: dicionário com um eixo (datas, períodos...) e listas paralelas de valores ----------
    @staticmethod
    def colunas(bloco, eixo):
        """Listas paralelas ao eixo: no próprio bloco ou um nível abaixo (ex.: empresas: {"periodos", "series": {...}};
        bancos: {"trimestres", "resumo": {...}, "carteiras": {...}})."""
        n = len(bloco.get(eixo) or [])
        cols = {k: v for k, v in bloco.items() if k != eixo and isinstance(v, list) and len(v) == n}
        for k, v in bloco.items():
            if isinstance(v, dict) and v and all(isinstance(x, list) and len(x) == n for x in v.values()):
                cols.update({f"{k}.{kk}": vv for kk, vv in v.items()})
        return cols

    def serie(self, arq, cam, antes, depois, eixo):
        da, dd = antes[eixo], depois.get(eixo) or []
        self.series += 1
        if not dd:
            self.problema(arq, cam, f"série ficou vazia (tinha {len(da)} pontos)")
            return
        ua, ud, pa, pd_ = _data(da[-1]), _data(dd[-1]), _data(da[0]), _data(dd[0])
        if ua and ud and ud < ua:
            self.problema(arq, cam, f"última data recuou de {da[-1]} para {dd[-1]}")
        if pa and pd_ and (pd_ - pa).days > MAX_ADIANTO_INICIO:
            self.problema(arq, cam, f"histórico encurtado: começava em {da[0]}, agora em {dd[0]}")
        novos = set(dd)
        buracos = [x for x in da if x not in novos and (_data(x) or date.min) >= (pd_ or date.min)]
        if len(buracos) > max(2, len(da) // 100):
            self.problema(arq, cam, f"{len(buracos)} pontos do histórico sumiram (ex.: {buracos[0]})")
        pos = {x: i for i, x in enumerate(dd)}
        cols_d = self.colunas(depois, eixo)
        for k, va in self.colunas(antes, eixo).items():
            vd = cols_d.get(k)
            if not isinstance(vd, list) or len(vd) != len(dd):
                if any(_numero(v) for v in va):
                    self.problema(arq, f"{cam}.{k}", "valores da série sumiram")
                continue
            # o último ponto antigo pode ainda estar em formação (semana ou mês corrente): mudança nele não é revisão
            mudou = [(x, a, vd[pos[x]]) for x, a in zip(da[:-1], va[:-1]) if x in pos and _numero(a)
                     and (not _numero(vd[pos[x]]) or abs(vd[pos[x]] - a) > TOLERANCIA * max(1.0, abs(a)))]
            if mudou:
                x, a, b = mudou[-1]
                self.revisao(arq, f"{cam}.{k}", len(mudou), f"{x}: {a} → {b}")

    # ---------- percurso genérico ----------
    def comparar(self, arq, cam, antes, depois):
        if isinstance(antes, dict):
            if not isinstance(depois, dict):
                if antes:
                    self.problema(arq, cam or "(raiz)", "estrutura mudou (deixou de ser um bloco de dados)")
                return
            eixo = next((e for e in EIXOS if isinstance(antes.get(e), list) and antes[e]), None)
            if eixo and self.colunas(antes, eixo):
                self.serie(arq, cam or "(raiz)", antes, depois, eixo)
            for k, va in antes.items():
                if k in IGNORAR_CHAVES or k == eixo:
                    continue
                c = f"{cam}.{k}" if cam else str(k)
                if k not in depois or depois[k] in (None, [], {}):
                    if _tem_historico(va):
                        self.problema(arq, c, "dado sumiu")
                    continue
                self.comparar(arq, c, va, depois[k])
        elif isinstance(antes, list) and antes and isinstance(antes[0], dict):
            if not isinstance(depois, list):
                self.problema(arq, cam, "lista virou outro tipo de dado")
                return
            # identificador de cada item: id, ticker, código; nas demonstrações, a conta ("c" ou "k")
            chave = next((c for c in ("id", "ticker", "cod", "link", "c", "k")
                          if all(isinstance(x, dict) and c in x for x in antes) and len({str(x[c]) for x in antes}) == len(antes)), None)
            if chave:
                novos = {x.get(chave): x for x in depois if isinstance(x, dict)}
                saiu = [x[chave] for x in antes if x[chave] not in novos]
                if saiu and chave != "link" and (len(saiu) > 3 or len(saiu) > len(antes) * 0.02):
                    self.problema(arq, cam, f"{len(saiu)} itens saíram da lista (ex.: {', '.join(map(str, saiu[:5]))})")
                for x in antes:
                    if x[chave] in novos:
                        self.comparar(arq, f"{cam}[{x[chave]}]", x, novos[x[chave]])
            elif len(depois) < len(antes) * 0.8 and not arq.startswith(ROLANTES):
                self.problema(arq, cam, f"lista encolheu de {len(antes)} para {len(depois)} itens")


def comparar_pastas(anterior, atual=DIR_DADOS_SITE):
    anterior, atual = Path(anterior), Path(atual)
    c = Comparacao()
    for p in sorted(anterior.rglob("*.json")):
        rel = p.relative_to(anterior).as_posix()
        if p.name in NAO_COMPARAR:
            continue
        novo = atual / rel
        c.arquivos += 1
        if not novo.exists():
            c.problema(rel, "", "arquivo sumiu")
            continue
        try:
            a, b = json.loads(p.read_text(encoding="utf-8")), json.loads(novo.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            c.problema(rel, "", f"arquivo ilegível ({type(e).__name__})")
            continue
        c.comparar(rel, "", a, b)
    return c


# ---------- quando cada dado chegou ao site (para o ⓘ dos gráficos) ----------
ARQ_CHEGADAS = DIR_INTERMEDIARIO / "chegadas.json"
# demonstrativos e formulários (empresas e bancos) mudam poucas vezes por ano: ficam de fora
SEM_CHEGADAS = ("empresas/", "fichas/", "negocio/", "eventos/", "resumos/", "bancos/")


def _ultimas_datas(obj, saida, nivel=0):
    """Última data de cada série do arquivo."""
    if isinstance(obj, dict):
        eixo = next((e for e in EIXOS if isinstance(obj.get(e), list) and obj[e]), None)
        if eixo and Comparacao.colunas(obj, eixo):
            saida.add(str(obj[eixo][-1]))
        if nivel < 6:
            for v in obj.values():
                _ultimas_datas(v, saida, nivel + 1)
    elif isinstance(obj, list) and nivel < 6:
        for v in obj[:600]:
            if isinstance(v, (dict, list)):
                _ultimas_datas(v, saida, nivel + 1)
    return saida


def registrar_chegadas(atual=DIR_DADOS_SITE):
    """Para cada arquivo e cada 'última data' de série, o momento em que ela apareceu pela primeira vez.
    No primeiro registro não se sabe quando os dados já existentes chegaram: ficam sem horário (null)."""
    agora = datetime.now(FUSO_BR).isoformat(timespec="minutes")
    try:
        reg = json.loads(ARQ_CHEGADAS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        reg = {"desde": agora, "chegadas": {}}
    inicial = not reg["chegadas"]
    novas = {}
    atual = Path(atual)
    for p in sorted(atual.rglob("*.json")):
        rel = p.relative_to(atual).as_posix()
        if p.name in NAO_COMPARAR or rel.startswith(SEM_CHEGADAS):
            continue
        try:
            datas = _ultimas_datas(json.loads(p.read_text(encoding="utf-8")), set())
        except (OSError, ValueError):
            continue
        if not datas:
            continue
        antes = reg["chegadas"].get(rel)
        novas[rel] = {d: (antes[d] if antes and d in antes else (None if inicial else agora))
                      for d in sorted(datas)}
    reg["chegadas"] = novas
    texto = json.dumps(reg, ensure_ascii=False, separators=(",", ":"))
    ARQ_CHEGADAS.write_text(texto, encoding="utf-8")
    (DIR_DADOS_SITE / "atualizacoes.json").write_text(texto, encoding="utf-8")
    return reg


def gerar(anterior):
    agora = datetime.now(FUSO_BR).isoformat(timespec="minutes")
    try:
        registrar_chegadas()
    except Exception as e:  # noqa: BLE001  (o registro do ⓘ não pode derrubar a comparação)
        print("⚠️ registro de chegadas:", repr(e)[:200])
    try:
        historico = json.loads(ARQ.read_text(encoding="utf-8")).get("historico", [])
    except (OSError, ValueError):
        historico = []
    if not Path(anterior).is_dir():
        saida = {"verificado_em": agora, "sem_anterior": True, "problemas": [], "recentes": [], "revisoes": {}, "historico": historico}
    else:
        c = comparar_pastas(anterior)
        limite = (datetime.now(FUSO_BR) - timedelta(days=DIAS_ALERTA)).isoformat(timespec="minutes")
        historico = [h for h in historico if h["em"] >= limite]
        # alarmes antigos de listas que andam com o tempo (regra posterior a eles) não ficam abertos
        removido = lambda p: str(p.get("caminho", "")).split(".")[0].split("[")[0] in REMOVIDOS_DE_PROPOSITO  # noqa: E731
        for h in historico:
            h["problemas"] = [p for p in h["problemas"] if not (p["arquivo"].startswith(ROLANTES) and "encolheu" in p["detalhe"]) and not removido(p)]
        c.problemas = [p for p in c.problemas if not removido(p)]
        historico = [h for h in historico if h["problemas"]]
        if c.problemas:
            historico.append({"em": agora, "problemas": c.problemas[:50]})
        saida = {
            "verificado_em": agora, "arquivos": c.arquivos, "series": c.series,
            "problemas": c.problemas[:200], "revisoes": c.revisoes,
            # problemas dos últimos DIAS_ALERTA dias (inclusive os desta execução), para não sumirem na seguinte
            "recentes": [dict(p, em=h["em"]) for h in historico for p in h["problemas"]][:100],
            "historico": historico,
        }
    texto = json.dumps(saida, ensure_ascii=False, indent=1)
    ARQ.write_text(texto, encoding="utf-8")
    (DIR_DADOS_SITE / "comparacao.json").write_text(texto, encoding="utf-8")
    if saida.get("sem_anterior"):
        print("ℹ️ comparação: sem versão anterior")
    else:
        print(f"{'❌' if saida['problemas'] else '✅'} comparação: {saida['arquivos']} arquivos, {saida['series']} séries; "
              f"{len(saida['problemas'])} problemas; revisões da fonte em {len(saida['revisoes'])} arquivos")
        for p in saida["problemas"][:20]:
            print(f"   ❌ {p['arquivo']} {p['caminho']}: {p['detalhe']}")
        for arq, r in list(saida["revisoes"].items())[:20]:
            print(f"   ↺ {arq}: {r['series']} séries, {r['pontos']} pontos revisados (ex.: {r['exemplo']})")
    return saida


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("uso: py -m pipeline.comparar PASTA_DOS_DADOS_ANTERIORES")
    gerar(sys.argv[1])
