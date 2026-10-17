"""
Validador de anomalias da R.V. Mapp (sem IA, roda no GitHub Actions depois da atualização).

Procura nos dados gerados sinais típicos de erro — não corrige nada, só lista para
conferir. Grava site/dados/validacao.json. Problemas graves (que afetam muitas
empresas, como base sem trimestre novo) também entram no alerta do monitor.

Uso: py -m pipeline.validar
"""

import json
import statistics
import sys
from datetime import date

from pipeline import DIR_DADOS_SITE, DIR_INTERMEDIARIO

ARQ_ALERTA = DIR_INTERMEDIARIO / "alerta.md"


def _pares(serie):
    return [(i, v) for i, v in enumerate(serie) if v is not None]


def checar_empresa(d):
    achados = []
    tri, ltm = d["trimestral"], d["ltm"]
    periodos, S = tri["periodos"], tri["series"]

    def add(tipo, detalhe, periodo=None):
        achados.append({"tipo": tipo, "detalhe": detalhe, "periodo": periodo})

    # 1) Receita negativa ou salto de escala (×100 de um trimestre para o outro)
    receita = S.get("receita", [])
    for i, v in _pares(receita):
        if v < 0:
            add("receita negativa", f"{v:,.0f}", periodos[i])
        if i and receita[i - 1] and receita[i - 1] > 0 and v > 0:
            razao = v / receita[i - 1]
            if razao > 100 or razao < 0.01:
                add("salto de escala na receita", f"×{razao:,.1f} contra o trimestre anterior", periodos[i])

    # 2) Margem bruta trimestral muito fora do padrão da própria empresa
    margens = [(i, v) for i, v in _pares(S.get("m_bruta", [])) if abs(v) < 5]
    if len(margens) >= 8:
        valores = [v for _, v in margens]
        mediana = statistics.median(valores)
        desvio = statistics.median([abs(v - mediana) for v in valores]) or 0.01
        for i, v in margens[-8:]:
            if abs(v - mediana) > 6 * desvio and abs(v - mediana) > 0.15:
                add("margem bruta fora do padrão", f"{v:.1%} (mediana {mediana:.1%})", periodos[i])

    # 3) D&A ou capex LTM negativos (linha errada somada por descrição)
    for serie, nome in (("da", "D&A"), ("capex", "capex")):
        valores = ltm["series"].get(serie, [])
        if valores and valores[-1] is not None and valores[-1] < 0:
            add(f"{nome} LTM negativo", f"{valores[-1]:,.0f}", ltm["periodos"][-1])

    # 4) Balanço que não fecha: caixa maior que o ativo total
    for i, (caixa, ativo) in enumerate(zip(S.get("caixa", []), S.get("ativo_total", []))):
        if caixa and ativo and caixa > ativo * 1.01:
            add("caixa maior que o ativo", f"caixa {caixa:,.0f} × ativo {ativo:,.0f}", periodos[i])

    # 5) Sem DFC (empresa que só publica pelo método direto) ou sem LTM
    if not any(v is not None for v in S.get("fco", [])):
        add("sem fluxo de caixa", "a CVM não traz DFC pelo método indireto")
    if not ltm["periodos"]:
        add("sem LTM", "não há 4 trimestres seguidos")
    return achados


def main():
    indice = json.loads((DIR_DADOS_SITE / "empresas.json").read_text(encoding="utf-8"))
    mercado_arq = DIR_DADOS_SITE / "mercado.json"
    mercado = {m["id"]: m for m in json.loads(mercado_arq.read_text(encoding="utf-8"))["empresas"]} if mercado_arq.exists() else {}

    por_empresa = {}
    for e in indice:
        d = json.loads((DIR_DADOS_SITE / "empresas" / f"{e['id']}.json").read_text(encoding="utf-8"))
        achados = checar_empresa(d)
        m = mercado.get(e["id"], {})
        if not m.get("market_cap"):
            achados.append({"tipo": "sem market cap", "detalhe": "sem cotação ou sem quantidade de ações", "periodo": None})
        cot = (m.get("cotacoes") or {}).get(m.get("papel_referencia") or "", {})
        if cot.get("data") and (date.today() - date.fromisoformat(cot["data"])).days > 7:
            achados.append({"tipo": "cotação defasada", "detalhe": f"último preço em {cot['data']} ({cot.get('fonte', 'B3')})", "periodo": None})
        if achados:
            por_empresa[e["id"]] = {"nome": e["nome"], "achados": achados}

    # Base sem trimestre novo: compara cada empresa com o período mais comum entre todas
    ultimos = [e["ultimo_periodo"] for e in indice if e["ultimo_periodo"]]
    mais_comum = max(set(ultimos), key=ultimos.count) if ultimos else None
    atrasadas = [e["id"] for e in indice if e["ultimo_periodo"] and mais_comum
                 and (date.fromisoformat(mais_comum) - date.fromisoformat(e["ultimo_periodo"])).days > 100]
    for id_ in atrasadas:
        por_empresa.setdefault(id_, {"nome": next(e["nome"] for e in indice if e["id"] == id_), "achados": []})
        por_empresa[id_]["achados"].append({"tipo": "sem trimestre novo",
                                            "detalhe": f"último período mais antigo que {mais_comum}", "periodo": None})

    contagem = {}
    for info in por_empresa.values():
        for a in info["achados"]:
            contagem[a["tipo"]] = contagem.get(a["tipo"], 0) + 1

    (DIR_DADOS_SITE / "validacao.json").write_text(json.dumps({
        "verificado_em": date.today().isoformat(), "periodo_mais_comum": mais_comum,
        "resumo": dict(sorted(contagem.items(), key=lambda x: -x[1])), "empresas": por_empresa,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"Validação: {len(por_empresa)} empresas com algum ponto a conferir")
    for tipo, n in sorted(contagem.items(), key=lambda x: -x[1]):
        print(f"   {n:4d}  {tipo}")

    # Grave o bastante para virar alerta: muitas empresas sem trimestre novo de uma vez
    # (sinal de que a base da CVM não foi atualizada) ou muitas sem market cap (B3 fora)
    graves = []
    if len(atrasadas) > 0.2 * len(indice):
        graves.append(f"{len(atrasadas)} empresas sem o trimestre mais recente ({mais_comum})")
    sem_mcap = contagem.get("sem market cap", 0)
    if sem_mcap > 0.2 * len(indice):
        graves.append(f"{sem_mcap} empresas sem market cap")
    if graves:
        texto = "\n".join(["", "**Validação dos dados:**", *[f"- {g}" for g in graves]])
        anterior = ARQ_ALERTA.read_text(encoding="utf-8") if ARQ_ALERTA.exists() else \
            f"O validador da R.V. Mapp encontrou problemas em {date.today():%d/%m/%Y}:"
        ARQ_ALERTA.write_text(anterior + "\n" + texto, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
