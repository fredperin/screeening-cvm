"""
Validador de anomalias da R.V. Mapp (sem IA, roda no GitHub Actions depois da atualização).

Procura nos dados gerados sinais típicos de erro — não corrige nada, só lista para
conferir. Grava site/dados/validacao.json. Problemas graves (que afetam muitas
empresas, como base sem trimestre novo) também entram no alerta do monitor.

Achados sérios (4º tri negativo ou muito fora do padrão do ano, salto de escala, caixa maior
que o ativo) são comparados com config/empresas_conferidas.json, a lista de casos já
examinados (com o motivo: igual à fonte, erro da própria empresa na CVM...). Só os NOVOS
viram observação no site (checagem "Dados das empresas (Brasil)" do monitor); os conhecidos
continuam listados em validacao.json.

Uso: py -m pipeline.validar
"""

import json
import statistics
import sys
from datetime import date, timedelta

from pipeline import DIR_DADOS_SITE, RAIZ

ARQ_CONFERIDAS = RAIZ / "config" / "empresas_conferidas.json"
ARQ_AUDITORIAS = RAIZ / "config" / "auditorias_empresas.json"  # conferências manuais contra o ITR/DFP do RI (aba Histórico de ajustes)
SERIOS = {"4º tri negativo", "4º tri fora do padrão do ano", "salto de escala na receita", "caixa maior que o ativo", "balanço não fecha"}
FATOR_4T = 3  # 4º tri mais de 3× acima (ou abaixo) da mediana dos outros 3 trimestres do mesmo exercício


def _mi(v):
    """Valor em R$ milhões no padrão brasileiro (aparece na aba Histórico de ajustes do site)."""
    return "R$ " + f"{v / 1e6:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + " mi"


def _pares(serie):
    return [(i, v) for i, v in enumerate(serie) if v is not None]


def checar_empresa(d):
    achados = []
    tri, ltm = d["trimestral"], d["ltm"]
    periodos, S = tri["periodos"], tri["series"]

    def add(tipo, detalhe, periodo=None):
        achados.append({"tipo": tipo, "detalhe": detalhe, "periodo": periodo})

    # 1) Receita negativa ou salto de escala (×100 de um trimestre para o outro). O 1º, 2º e 3º tri
    # isolados vêm publicados pela empresa; o 4º é calculado (ano − 9 meses), por isso pesa mais.
    receita = S.get("receita", [])
    mes_fim = d.get("mes_fim_exercicio") or 12
    for i, v in _pares(receita):
        quarto = int(periodos[i][5:7]) == mes_fim
        if v < 0:
            add("4º tri negativo" if quarto else "receita negativa publicada pela empresa", f"{_mi(v)}", periodos[i])
        outros = [x for x in receita[max(0, i - 3):i] if x is not None]
        if quarto and v > 0 and len(outros) == 3 and statistics.median(outros) > 50e6:
            m = statistics.median(outros)
            if v > FATOR_4T * m or v < m / FATOR_4T:
                add("4º tri fora do padrão do ano", f"{_mi(v)} (mediana dos outros trimestres {_mi(m)})", periodos[i])
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
            add(f"{nome} LTM negativo", f"{_mi(valores[-1])}", ltm["periodos"][-1])

    # 4) Balanço que não fecha: caixa maior que o ativo total
    for i, (caixa, ativo) in enumerate(zip(S.get("caixa", []), S.get("ativo_total", []))):
        if caixa and ativo and caixa > ativo * 1.01:
            add("caixa maior que o ativo", f"caixa {_mi(caixa)} × ativo {_mi(ativo)}", periodos[i])

    # 6) Balanço que não fecha: ativo total ≠ passivo total (identidade contábil — diferença indica dado misturado)
    for i, (ativo, passivo) in enumerate(zip(S.get("ativo_total", []), S.get("passivo_total", []))):
        if ativo and passivo and abs(ativo - passivo) > 0.005 * abs(ativo):
            add("balanço não fecha", f"ativo total {_mi(ativo)} × passivo total {_mi(passivo)}", periodos[i])

    # 7) DFC × balanço: variação de caixa da DFC (6.05) contra a variação do caixa e equivalentes do balanço (1.01.01),
    # em trimestres seguidos. Diferença pode ser legítima (caixa da DFC com outra definição), por isso é só para conferir.
    # Se a diferença aparece na maior parte dos trimestres, a DFC usa outra definição de caixa (ex.: inclui aplicações):
    # vira um único registro, em vez de um por trimestre.
    caixa, var = S.get("caixa", []), S.get("var_caixa", [])
    ativos = S.get("ativo_total", [])
    conferidos, diferentes = 0, []
    for i in range(1, min(len(periodos), len(caixa), len(var))):
        if None in (caixa[i - 1], caixa[i], var[i]):
            continue
        if (date.fromisoformat(periodos[i]) - date.fromisoformat(periodos[i - 1])).days > 100:
            continue
        conferidos += 1
        variacao = caixa[i] - caixa[i - 1]
        if abs(variacao - var[i]) > max(5e6, 0.01 * abs(ativos[i] or 0)):
            diferentes.append((periodos[i], f"variação do caixa no balanço {_mi(variacao)} × DFC {_mi(var[i])}"))
    if conferidos and len(diferentes) > 0.4 * conferidos:
        add("DFC com outra definição de caixa", f"a variação de caixa da DFC difere da do balanço em {len(diferentes)} de {conferidos} trimestres "
            "(a DFC da empresa usa outra definição de caixa e equivalentes)")
    else:
        for per, detalhe in diferentes:
            add("DFC não fecha com o caixa", detalhe, per)

    # 8) Soma dos 4 trimestres × ano oficial (DFP): diferença indica reapresentação de algum trimestre
    anual = d.get("anual") or {}
    mapa_tri = {p: i for i, p in enumerate(periodos)}
    for serie, nome in (("receita", "receita"), ("lucro_liquido", "lucro líquido")):
        valores_ano, valores_tri = (anual.get("series") or {}).get(serie, []), S.get(serie, [])
        for j, fim in enumerate(anual.get("periodos") or []):
            v_ano = valores_ano[j] if j < len(valores_ano) else None
            f = date.fromisoformat(fim)
            datas = [f]
            for _ in range(3):
                ant = date(datas[-1].year - (datas[-1].month <= 3), (datas[-1].month - 4) % 12 + 1, 1)
                datas.append(date(ant.year + (ant.month == 12), ant.month % 12 + 1, 1) - timedelta(days=1))
            idx = [mapa_tri.get(x.isoformat()) for x in datas]
            if v_ano is None or None in idx or any(valores_tri[k] is None for k in idx):
                continue
            soma = sum(valores_tri[k] for k in idx)
            if abs(soma - v_ano) > max(1e6, 0.005 * abs(v_ano)):
                add("soma dos trimestres ≠ ano (reapresentação)", f"{nome}: ano oficial {_mi(v_ano)} × soma dos 4 trimestres {_mi(soma)}", fim)

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

    # Achados sérios: novos (ainda não examinados) × conhecidos (na lista de conferidos, com o motivo)
    conferidas = json.loads(ARQ_CONFERIDAS.read_text(encoding="utf-8")).get("casos", {}) if ARQ_CONFERIDAS.exists() else {}
    novos, conhecidos = [], []
    for id_, info in por_empresa.items():
        for a in info["achados"]:
            if a["tipo"] not in SERIOS:
                continue
            chave = f"{id_}|{a['periodo']}|{a['tipo']}"
            item = {"chave": chave, "empresa": id_, "periodo": a["periodo"], "tipo": a["tipo"], "detalhe": a["detalhe"]}
            if chave in conferidas:
                conhecidos.append({**item, "motivo": conferidas[chave]})
            else:
                novos.append(item)

    # Grave o bastante para virar alerta: muitas empresas sem trimestre novo de uma vez
    # (sinal de que a base da CVM não foi atualizada) ou muitas sem market cap (B3 fora).
    # Vai no validacao.json; o monitor (que roda depois) leva às Observações e ao alerta por e-mail.
    graves = []
    if len(atrasadas) > 0.2 * len(indice):
        graves.append(f"{len(atrasadas)} empresas sem o trimestre mais recente ({mais_comum})")
    sem_mcap = contagem.get("sem market cap", 0)
    if sem_mcap > 0.2 * len(indice):
        graves.append(f"{sem_mcap} empresas sem market cap")

    (DIR_DADOS_SITE / "validacao.json").write_text(json.dumps({
        "verificado_em": date.today().isoformat(), "periodo_mais_comum": mais_comum,
        "resumo": dict(sorted(contagem.items(), key=lambda x: -x[1])), "empresas": por_empresa,
        "serios_novos": novos, "serios_conhecidos": conhecidos, "graves": graves,
        # conferências manuais contra o ITR/DFP publicado no RI, por empresa (config/auditorias_empresas.json)
        "auditorias": json.loads(ARQ_AUDITORIAS.read_text(encoding="utf-8")).get("auditorias", {}) if ARQ_AUDITORIAS.exists() else {},
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"Validação: {len(por_empresa)} empresas com algum ponto a conferir; achados sérios: {len(novos)} novos, {len(conhecidos)} já conferidos")
    for n in novos[:30]:
        print(f"   🆕 {n['empresa']} {n['periodo']}: {n['tipo']} — {n['detalhe']}")
    for tipo, n in sorted(contagem.items(), key=lambda x: -x[1]):
        print(f"   {n:4d}  {tipo}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
