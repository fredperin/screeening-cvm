"""
Séries de uma empresa para o site: a partir dos blocos do documento padrão
(DRE e DFC em trimestre isolado, Balanço na data), monta as visões trimestral,
semestral (só semestres fechados), anual (só anos fechados) e LTM.

As definições dos indicadores são as mesmas da aba "Indicadores (LTM)" do
Excel (src/indicadores.py) — inclusive D&A e capex identificados por descrição.
"""

import math
import re
from datetime import datetime

import pandas as pd

from src.indicadores import EXCLUI_CAPEX, EXCLUI_DA, PADRAO_CAPEX, PADRAO_DA

ESCALAS = {"MIL": 1000, "UNIDADE": 1}
PADRAO_DIV = re.compile(r"dividend|juros sobre (?:o )?capital|\bjcp\b", re.I)
EXCLUI_DIV = re.compile(r"receb", re.I)

FLUXOS = {
    "receita": "3.01", "lucro_bruto": "3.03", "ebit": "3.05", "res_fin": "3.06",
    "rec_fin": "3.06.01", "desp_fin": "3.06.02", "lair": "3.07", "ir": "3.08",
    "lucro_liquido": "3.11", "fco": "6.01",
}
SALDOS = {
    "ativo_total": "1", "ativo_circ": "1.01", "caixa": "1.01.01", "aplicacoes": "1.01.02",
    "passivo_circ": "2.01", "emprest_cp": "2.01.04", "emprest_lp": "2.02.01", "pl": "2.03",
}


def _por_codigo(df, fator):
    t = df.copy()
    t.index = df.attrs["codigos"]
    t.columns = [datetime.strptime(c, "%d/%m/%y").date() for c in df.columns]
    return t * fator


def linhas_dfc(base):
    """
    Linhas da DFC indireta prontas para somar por descrição: em R$, com o rótulo do
    período e, para cada período, SÓ o envio mais recente que o contém (consolidado
    quando houver). Isso importa porque os códigos de nível 3/4 da DFC são próprios
    de cada empresa e mudam de significado entre anos (a Klabin lançava dividendos em
    6.03.05 até 2022 e em 6.03.08 depois) — por isso cada linha é identificada pela
    descrição DO PRÓPRIO envio, nunca pela descrição mais recente daquele código.
    """
    d = base[(base["SIGLA"] == "DFC_MI") & base["DT_INI_EXERC"].notna()].copy()
    if d.empty:
        return d
    fim = pd.to_datetime(d["DT_FIM_EXERC"])
    fev = (fim.dt.month == 2) & (fim.dt.day == 28) & fim.dt.is_leap_year
    d["DT_FIM_EXERC"] = fim.where(~fev, fim + pd.offsets.MonthEnd(0)).dt.strftime("%Y-%m-%d")
    d["PER"] = d["DT_INI_EXERC"] + " a " + d["DT_FIM_EXERC"]
    d["VL"] = d["VL_CONTA"] * d["ESCALA_MOEDA"].map(ESCALAS).fillna(1)
    com_con = set(d.loc[d["TIPO"] == "con", "PER"])
    d = d[(d["TIPO"] == "con") == d["PER"].isin(com_con)]
    d["_ENVIO"] = d["DT_REFER"] + "|" + d["VERSAO"].astype(str).str.zfill(3)
    return d[d["_ENVIO"] == d.groupby("PER")["_ENVIO"].transform("max")]


def serie_por_descricao(linhas, prefixo, padrao, exclui):
    """
    Soma, por período, as linhas cuja descrição casa com o padrão e isola cada
    trimestre. Devolve (trimestral {data_fim: valor}, anual {data_fim: valor}, descrições usadas).
    """
    from src.padrao_visual import isolar_trimestres

    if linhas.empty:
        return {}, {}, []
    nivel = prefixo.count(".") + 1
    cd = linhas["CD_CONTA"]
    casa = (cd.str.startswith(prefixo + ".") & (cd.str.count(r"\.") == nivel)
            & linhas["DS_CONTA"].str.contains(padrao) & ~linhas["DS_CONTA"].str.contains(exclui))
    escolhidas = linhas[casa]
    soma = escolhidas.groupby("PER")["VL"].sum().reindex(sorted(linhas["PER"].unique()), fill_value=0.0)
    isolada = isolar_trimestres(pd.DataFrame([soma]), preferir_derivado=True).iloc[0]
    tri = {datetime.strptime(c.split(" a ")[1], "%Y-%m-%d").date(): v for c, v in isolada.items()}
    anual = {}
    for per, v in soma.items():
        ini, fim = per.split(" a ")
        if (pd.Timestamp(fim) - pd.Timestamp(ini)).days >= 360:
            anual[datetime.strptime(fim, "%Y-%m-%d").date()] = v
    return tri, anual, sorted(escolhidas["DS_CONTA"].str.strip().unique())


SERIES_DESCRICAO = {
    "da": ("6.01.01", PADRAO_DA, EXCLUI_DA, 1),
    "capex": ("6.02", PADRAO_CAPEX, EXCLUI_CAPEX, -1),
    "div_pagos": ("6.03", PADRAO_DIV, EXCLUI_DIV, -1),
}


def _consecutivos(datas):
    return all(70 <= (b - a).days <= 105 for a, b in zip(datas, datas[1:]))


def montar_trimestral(blocos, fator, base):
    """DataFrame com uma linha por trimestre (índice = data de fim) e as séries base em R$."""
    por_titulo = {t: d for t, d in blocos if d is not None and not d.empty}
    dre = _por_codigo(por_titulo["DRE"], fator)
    bp = _por_codigo(por_titulo["Balanço Patrimonial"], fator)
    if "DFC (Método Indireto)" in por_titulo:
        dfc = _por_codigo(por_titulo["DFC (Método Indireto)"], fator)
    else:  # empresa que só publica DFC pelo método direto: séries de caixa ficam vazias
        dfc = pd.DataFrame(columns=dre.columns, dtype=float)

    def linha(tab, cd):
        return tab.loc[cd] if cd in tab.index else pd.Series(float("nan"), index=tab.columns)

    q = pd.DataFrame(index=dre.columns)
    for nome, cd in FLUXOS.items():
        q[nome] = linha(dfc if cd.startswith("6") else dre, cd)
    for nome, cd in SALDOS.items():
        q[nome] = linha(bp, cd)

    linhas = linhas_dfc(base)
    notas = {}
    tem_dfc = len(dfc) > 0
    for nome, (prefixo, padrao, exclui, sinal) in SERIES_DESCRICAO.items():
        tri, _, usadas = serie_por_descricao(linhas, prefixo, padrao, exclui)
        valores = pd.Series({d: tri.get(d, 0.0 if tem_dfc else float("nan")) for d in q.index})
        q[nome] = sinal * valores
        notas[{"da": "da", "capex": "capex", "div_pagos": "dividendos"}[nome]] = usadas
    q["ebitda"] = q["ebit"] + q["da"]
    q["fcf"] = q["fco"] - q["capex"]
    q["divida_bruta"] = q[["emprest_cp", "emprest_lp"]].sum(axis=1, min_count=1)
    q["divida_liquida"] = q["divida_bruta"].fillna(0) - q["caixa"].fillna(0) - q["aplicacoes"].fillna(0)
    q = q.sort_index()
    return q, notas


FLUXOS_TODOS = list(FLUXOS) + ["da", "capex", "div_pagos", "ebitda", "fcf"]
SALDOS_TODOS = list(SALDOS) + ["divida_bruta", "divida_liquida"]


def _agregar(q, grupos):
    """grupos: lista de (data_fim, [datas dos trimestres]) — soma fluxos, saldo = fim do período."""
    linhas = {}
    for fim, datas in grupos:
        bloco = q.loc[datas]
        valores = bloco[FLUXOS_TODOS].sum(min_count=len(datas))
        linhas[fim] = pd.concat([valores, q.loc[fim, SALDOS_TODOS]])
    return pd.DataFrame(linhas).T if linhas else pd.DataFrame(columns=FLUXOS_TODOS + SALDOS_TODOS)


def _mes_anterior(ano, mes, n):
    total = ano * 12 + (mes - 1) - n
    return total // 12, total % 12 + 1


def montar_visoes(q, mes_fim_exercicio=12):
    """
    Semestre e ano só entram fechados (todos os trimestres publicados), seguindo o
    exercício da empresa: com fechamento em março (São Martinho), o "ano" vai de
    abril a março e os semestres terminam em setembro e março.
    """
    datas = list(q.index)
    por_ano_mes = {(d.year, d.month): d for d in datas}

    mes_fim_1s = _mes_anterior(2000, mes_fim_exercicio, 6)[1]
    semestres, anos = [], []
    for d in datas:
        if d.month not in (mes_fim_exercicio, mes_fim_1s):
            continue
        anterior = por_ano_mes.get(_mes_anterior(d.year, d.month, 3))
        if anterior:
            semestres.append((d, [anterior, d]))
        if d.month == mes_fim_exercicio:
            trimestres = [por_ano_mes.get(_mes_anterior(d.year, d.month, n)) for n in (9, 6, 3, 0)]
            if all(trimestres):
                anos.append((d, trimestres))

    ltm = [(datas[j], datas[j - 3: j + 1]) for j in range(3, len(datas)) if _consecutivos(datas[j - 3: j + 1])]

    return {
        "trimestral": q[FLUXOS_TODOS + SALDOS_TODOS].copy(),
        "semestral": _agregar(q, semestres),
        "anual": _agregar(q, anos),
        "ltm": _agregar(q, ltm),
    }


def fluxos_anuais_dfp(base):
    """
    Fluxos anuais direto da DFP (o número oficial do ano), em R$, um por data de fim
    de exercício. A soma dos 4 trimestres pode divergir quando a empresa reapresenta
    um trimestre num envio posterior (ex: Raízen 2025/26) — por isso a visão anual usa estes.
    """
    dfp = base[(base["FONTE"] == "DFP") & base["SIGLA"].isin(["DRE", "DFC_MI"]) & base["DT_INI_EXERC"].notna()].copy()
    if dfp.empty:
        return pd.DataFrame()
    dias = (pd.to_datetime(dfp["DT_FIM_EXERC"]) - pd.to_datetime(dfp["DT_INI_EXERC"])).dt.days
    dfp = dfp[dias >= 360]
    fim = pd.to_datetime(dfp["DT_FIM_EXERC"])
    fev = (fim.dt.month == 2) & (fim.dt.day == 28) & fim.dt.is_leap_year
    dfp["DT_FIM_EXERC"] = fim.where(~fev, fim + pd.offsets.MonthEnd(0)).dt.date
    # consolidado quando houver para aquele ano, senão individual (mesma regra do documento padrão)
    tem_con = dfp[dfp["TIPO"] == "con"].groupby("DT_FIM_EXERC")["SIGLA"].nunique() == 2
    usar_con = dfp["DT_FIM_EXERC"].map(tem_con).fillna(False).astype(bool)
    dfp = dfp[(dfp["TIPO"] == "con") == usar_con]
    dfp = dfp.sort_values(["DT_REFER", "VERSAO"]).drop_duplicates(["CD_CONTA", "DT_FIM_EXERC"], keep="last")
    dfp["VL"] = dfp["VL_CONTA"] * dfp["ESCALA_MOEDA"].map(ESCALAS).fillna(1)

    tabela = dfp.pivot_table(index="CD_CONTA", columns="DT_FIM_EXERC", values="VL", aggfunc="first")

    a = pd.DataFrame(index=tabela.columns)
    for nome, cd in FLUXOS.items():
        a[nome] = tabela.loc[cd] if cd in tabela.index else float("nan")
    linhas = linhas_dfc(base)
    for nome, (prefixo, padrao, exclui, sinal) in SERIES_DESCRICAO.items():
        _, anual, _ = serie_por_descricao(linhas, prefixo, padrao, exclui)
        a[nome] = [sinal * anual[d] if d in anual else float("nan") for d in a.index]
    a["ebitda"] = a["ebit"] + a["da"]
    a["fcf"] = a["fco"] - a["capex"]
    return a


def aplicar_anual_dfp(visoes, base):
    anual_dfp = fluxos_anuais_dfp(base)
    v = visoes["anual"]
    if anual_dfp.empty or v.empty:
        return visoes
    datas = [d for d in v.index if d in anual_dfp.index]
    for col in FLUXOS_TODOS:
        v.loc[datas, col] = anual_dfp.loc[datas, col].fillna(0.0).values if col in ("da", "capex", "div_pagos") else anual_dfp.loc[datas, col].values
    return visoes


def _div(a, b):
    return a / b.where(b != 0)


def _um_ano_antes(serie):
    """Valor do mesmo período um ano antes (mesmo mês — o dia muda em fevereiro de ano bissexto), ou NaN."""
    mapa = {(d.year, d.month): v for d, v in zip(serie.index, serie.values)}
    return pd.Series([mapa.get((d.year - 1, d.month), float("nan")) for d in serie.index], index=serie.index)


def adicionar_indicadores(visoes, aliquota=0.34):
    ltm = visoes["ltm"]
    for nome, v in visoes.items():
        if v.empty:
            continue
        v["m_bruta"] = _div(v["lucro_bruto"], v["receita"])
        v["m_ebitda"] = _div(v["ebitda"], v["receita"])
        v["m_ebit"] = _div(v["ebit"], v["receita"])
        v["m_liquida"] = _div(v["lucro_liquido"], v["receita"])
        v["m_fcf"] = _div(v["fcf"], v["receita"])
        v["cresc_receita"] = _div(v["receita"], _um_ano_antes(v["receita"])) - 1
        v["cresc_lucro"] = _div(v["lucro_liquido"], _um_ano_antes(v["lucro_liquido"])) - 1
        v["payout"] = _div(v["div_pagos"], v["lucro_liquido"])
        v["aliquota_efetiva"] = _div(-v["ir"], v["lair"])
        v["capex_receita"] = _div(v["capex"], v["receita"])
        v["capex_da"] = _div(v["capex"], v["da"])
        v["liquidez_corrente"] = _div(v["ativo_circ"], v["passivo_circ"])
        v["dl_pl"] = _div(v["divida_liquida"], v["pl"])

        # Múltiplos e retornos sempre sobre o LTM da mesma data, em qualquer visão
        base = ltm.reindex(v.index)
        v["dl_ebitda"] = _div(v["divida_liquida"], base["ebitda"])
        v["roe"] = _div(base["lucro_liquido"], v["pl"])
        v["roa"] = _div(base["lucro_liquido"], v["ativo_total"])
        v["roic"] = _div(base["ebit"] * (1 - aliquota), v["divida_liquida"] + v["pl"])
        v["cobertura_juros"] = _div(base["ebit"], -base["desp_fin"])
        v["conv_caixa"] = _div(base["fco"], base["ebitda"])
        v["conv_lucro"] = _div(base["fcf"], base["lucro_liquido"])
    return visoes


def _limpar(v):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return None
    return round(float(v), 2) if abs(v) >= 100 else round(float(v), 6)


def para_json(visoes):
    saida = {}
    for nome, v in visoes.items():
        v = v.sort_index()
        saida[nome] = {
            "periodos": [d.isoformat() for d in v.index],
            "series": {col: [_limpar(x) for x in v[col].astype(float)] for col in v.columns},
        }
    return saida
