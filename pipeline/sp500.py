"""
S&P 500 como um todo (Mundo → Empresas → S&P 500): soma das empresas do índice, como a própria S&P calcula o lucro
do índice (sem ponderar pelo peso, que já é o tamanho de cada empresa). Nenhuma consulta nova: usa os arquivos que
pipeline/empresas_mundo.py gera a partir da SEC (balanços XBRL dos 10-K/10-Q, ações em circulação), as cotações
semanais (Yahoo) e o índice do FRED (pipeline/mundo.py).

- Fluxos (receita, EBITDA, lucro, capex, fluxo de caixa livre): soma por trimestre-calendário (o período de cada
  empresa vai para o fim de trimestre mais próximo) e por ano-calendário (só empresas com os 4 trimestres).
- Crescimento: sempre sobre o mesmo conjunto de empresas nos dois períodos.
- Indicadores: soma sobre soma (ROE = lucro ÷ patrimônio; ROIC = EBIT × (1 − 21%) ÷ (patrimônio + dívida líquida);
  dívida líquida ÷ EBITDA; P/L = valor de mercado ÷ lucro de 12 meses; FCF yield = fluxo de caixa livre ÷ valor de mercado).
- Financeiras (bancos, seguradoras, corretoras; SIC 6000–6499 e 6700–6799, exceto REITs) ficam fora de EBITDA, capex,
  fluxo de caixa livre, dívida e ROIC, que não se aplicam a elas; entram em receita, lucro, ROE e P/L.
- Composição: a atual do índice (empresas que saíram no passado não entram).

Saída: site/dados/sp500.json. Uso: py -m pipeline.sp500
"""

import json
from datetime import datetime, timedelta, timezone

import pandas as pd

from pipeline import DIR_DADOS_SITE

ARQ = DIR_DADOS_SITE / "sp500.json"
DIR_EMP = DIR_DADOS_SITE / "mundo_empresas"
FUSO_BR = timezone(timedelta(hours=-3))
INICIO = pd.Timestamp("2010-01-01")
ALIQUOTA = 0.21          # mesma alíquota usada no ROIC de cada empresa americana
DEFASAGEM_BALANCO = 45   # dias entre o fim do trimestre e o balanço ser conhecido (P/L histórico sem olhar o futuro)
FLUXOS = {"receita": "receita", "ebitda": "ebitda", "lucro": "lucro_liquido", "capex": "capex", "fcf": "fcf"}
SO_NAO_FINANCEIRAS = {"ebitda", "capex", "fcf", "divida_liquida"}


# Setor a partir do código de atividade da SEC (SIC), agrupado nos 11 setores conhecidos do mercado. É uma aproximação
# do GICS (que é pago): ex.: Alphabet e Meta (SIC 7370) caem em Tecnologia, e não em Comunicação.
REGRAS_SETOR = [  # (de, até, setor) — a primeira faixa que contém o código vale; exceções antes das faixas largas
    (6324, 6324, "Saúde"), (6798, 6798, "Imobiliário"), (6500, 6599, "Imobiliário"), (6000, 6799, "Financeiro"),
    (1311, 1389, "Energia"), (2911, 2999, "Energia"), (4922, 4923, "Energia"), (5171, 5172, "Energia"),
    (4953, 4959, "Industrial"), (4900, 4999, "Utilidades públicas"),
    (2833, 2836, "Saúde"), (3841, 3851, "Saúde"), (5047, 5047, "Saúde"), (5122, 5122, "Saúde"), (8000, 8099, "Saúde"), (8731, 8734, "Saúde"),
    (3570, 3579, "Tecnologia"), (3660, 3679, "Tecnologia"), (3810, 3829, "Tecnologia"), (7370, 7379, "Tecnologia"), (3577, 3577, "Tecnologia"),
    (4800, 4899, "Comunicação"), (2710, 2799, "Comunicação"), (7810, 7899, "Comunicação"),
    (2000, 2199, "Consumo básico"), (2840, 2844, "Consumo básico"), (5140, 5149, "Consumo básico"), (5411, 5411, "Consumo básico"),
    (5331, 5331, "Consumo básico"), (5399, 5399, "Consumo básico"), (5912, 5912, "Consumo básico"), (2080, 2087, "Consumo básico"),
    (3711, 3716, "Consumo discricionário"), (3751, 3751, "Consumo discricionário"), (1531, 1531, "Consumo discricionário"),
    (2300, 2399, "Consumo discricionário"), (2500, 2599, "Consumo discricionário"), (3100, 3199, "Consumo discricionário"),
    (3630, 3639, "Consumo discricionário"), (3940, 3949, "Consumo discricionário"), (5000, 5999, "Consumo discricionário"),
    (7000, 7099, "Consumo discricionário"), (7900, 7999, "Consumo discricionário"), (8200, 8299, "Consumo discricionário"),
    (1000, 1499, "Materiais"), (2400, 2699, "Materiais"), (2800, 2899, "Materiais"), (3000, 3099, "Materiais"),
    (3200, 3399, "Materiais"), (3410, 3412, "Materiais"),
    (1500, 1799, "Industrial"), (3400, 3999, "Industrial"), (4000, 4799, "Industrial"), (7300, 7399, "Industrial"), (8700, 8799, "Industrial"),
]


# Empresas conhecidas em que o SIC destoa do setor usado pelo mercado
SETOR_POR_TICKER = {
    **{k: "Financeiro" for k in ("V", "MA", "PYPL", "FIS", "FI", "GPN", "CPAY", "AXP", "COF", "SYF")},
    **{k: "Comunicação" for k in ("GOOGL", "META", "DIS", "EA", "TTWO", "WBD", "PARA", "FOXA", "NWSA", "OMC", "IPG", "LYV", "MTCH", "CHTR", "CMCSA")},
}


def setor(sic, ticker=None):
    if ticker in SETOR_POR_TICKER:
        return SETOR_POR_TICKER[ticker]
    try:
        s = int(str(sic or "0")[:4])
    except ValueError:
        return "Outros"
    return next((nome for de, ate, nome in REGRAS_SETOR if de <= s <= ate), "Outros")


def _financeira(sic):
    try:
        s = int(str(sic or "0")[:4])
    except ValueError:
        return False
    return (6000 <= s <= 6499 or 6700 <= s <= 6799) and s != 6798


def _trimestre(data):
    """Fim de trimestre-calendário mais próximo da data (mar, jun, set, dez)."""
    d = pd.Timestamp(data)
    m = d.year * 12 + d.month - 1
    q = min((m - (m % 3) + 2, m - (m % 3) - 1), key=lambda x: abs(x - m))  # 2 = março no índice do mês (0 = jan)
    return pd.Timestamp(q // 12, q % 12 + 1, 1) + pd.offsets.MonthEnd(0)


def _ajustar_desdobramentos(hist):
    """Ações da SEC vêm como divulgadas (antes e depois de cada desdobramento); os preços do Yahoo vêm ajustados.
    Saltos que são múltiplos inteiros (2×, 3×, 4×, 10×, 20×… ou o inverso) são tratados como desdobramento e as
    quantidades anteriores são corrigidas pelo mesmo fator."""
    if not hist:
        return pd.Series(dtype=float)
    s = pd.Series({pd.Timestamp(d): float(v) for d, v in hist if v}).sort_index()
    s = s[s > 0]
    vals = s.values.copy()
    for i in range(len(vals) - 1, 0, -1):
        r = vals[i] / vals[i - 1]
        fator = None
        if r >= 1.8 and abs(r - round(r)) <= 0.03 * r:
            fator = round(r)
        elif r <= 0.55 and abs(1 / r - round(1 / r)) <= 0.03 / r:
            fator = 1 / round(1 / r)
        if fator:
            vals[:i] = vals[:i] * fator
    return pd.Series(vals, index=s.index)


def _empresa(arq):
    d = json.loads(arq.read_text(encoding="utf-8"))
    fin = _financeira((d.get("cadastro") or {}).get("sic"))

    def bloco(nome):
        b = d.get(nome) or {}
        if not b.get("periodos"):
            return pd.DataFrame()
        df = pd.DataFrame(b["series"], index=[_trimestre(p) for p in b["periodos"]]).apply(pd.to_numeric, errors="coerce")
        return df[~df.index.duplicated(keep="last")].sort_index()

    cot = d.get("cotacao_semanal") or {}
    precos = pd.Series(cot.get("fechamento") or [], index=pd.to_datetime(cot.get("datas") or []), dtype=float)
    return {"id": d["id"], "fin": fin, "setor": setor((d.get("cadastro") or {}).get("sic"), d["id"]), "tri": bloco("trimestral"), "ltm": bloco("ltm"), "precos": precos,
            "acoes": _ajustar_desdobramentos(d.get("acoes_hist"))}


LIMITE_RECEITA = 5    # valor do trimestre acima de 5× a receita da empresa no trimestre…
LIMITE_HISTORICO = 100  # …e acima de 100× o normal da própria empresa (mediana dos trimestres vizinhos): erro de escala
# no XBRL costuma ser de 1.000× (milhões informados como bilhões); baixas contábeis e indenizações reais ficam bem abaixo


def _plausiveis(tab, receitas, descartados, chave):
    """Tira da soma só valores impossíveis: muito acima da receita da empresa no trimestre E muito fora do padrão dela
    (ex.: depreciação informada em bilhões em vez de milhões). Prejuízos grandes de quem quase não tem receita (biotecnologia)
    continuam, porque são o padrão da empresa. A página da empresa continua mostrando o que a fonte informou."""
    if chave in ("receita", "divida_liquida"):
        return tab
    rec = receitas.reindex(index=tab.index, columns=tab.columns).abs()
    normal = tab.abs().rolling(9, center=True, min_periods=4).median()
    ruim = (tab.abs() > LIMITE_RECEITA * rec) & (rec > 0) & (tab.abs() > LIMITE_HISTORICO * normal)
    for data, emp in zip(*ruim.values.nonzero()):
        descartados.append(f"{tab.columns[emp]} {tab.index[data]:%Y-%m}: {chave} {tab.iat[data, emp] / 1e6:,.0f} mi "
                           f"(receita {rec.iat[data, emp] / 1e6:,.0f} mi; normal da empresa {normal.iat[data, emp] / 1e6:,.0f} mi)")
    return tab.mask(ruim)


def _soma_e_crescimento(tabela, defasagem):
    """Soma por período e crescimento sobre o mesmo conjunto de empresas (período × período − defasagem)."""
    soma = tabela.sum(axis=1, min_count=1)
    cresc = {}
    for i, p in enumerate(tabela.index):
        if i < defasagem:
            continue
        a, b = tabela.iloc[i], tabela.iloc[i - defasagem]
        comuns = a.notna() & b.notna()
        if comuns.sum() >= 50 and b[comuns].sum() != 0:
            cresc[p] = (a[comuns].sum() / b[comuns].sum() - 1) * 100
    return soma, pd.Series(cresc, dtype=float), tabela.notna().sum(axis=1)


def _pacote(s, casas=1):
    s = s.dropna()
    return {"datas": [d.strftime("%Y-%m-%d") for d in s.index], "valores": [round(float(v), casas) for v in s.values]}


def gerar():
    empresas = [_empresa(a) for a in sorted(DIR_EMP.glob("*.json"))]
    if len(empresas) < 300:
        raise RuntimeError(f"só {len(empresas)} empresas do S&P 500 disponíveis")
    trimestres = pd.date_range(INICIO, pd.Timestamp.today(), freq="QE")
    # trimestre ainda em divulgação (poucas empresas já entregaram o balanço) fica de fora
    n_receita = pd.DataFrame({e["id"]: e["tri"]["receita"].reindex(trimestres) for e in empresas if "receita" in e["tri"]},
                             index=trimestres).notna().sum(axis=1)
    while len(trimestres) > 8 and n_receita[trimestres[-1]] < 0.9 * n_receita[trimestres[-2]]:
        trimestres = trimestres[:-1]
    receitas = pd.DataFrame({e["id"]: e["tri"]["receita"].reindex(trimestres) for e in empresas if "receita" in e["tri"]}, index=trimestres)
    tri, anual, cobertura, descartados = {}, {}, {}, []
    for chave, campo in {**FLUXOS, "divida_liquida": "divida_liquida"}.items():
        cols = {e["id"]: e["tri"][campo].reindex(trimestres) for e in empresas
                if campo in e["tri"] and not (e["fin"] and chave in SO_NAO_FINANCEIRAS)}
        tab = _plausiveis(pd.DataFrame(cols, index=trimestres), receitas, descartados, chave)
        if chave == "divida_liquida":  # saldo: fim de cada trimestre / fim de cada ano
            soma, cresc, n = _soma_e_crescimento(tab, 4)
            fim_ano = tab[tab.index.month == 12]
            soma_a, cresc_a, _ = _soma_e_crescimento(fim_ano, 1)
        else:
            soma, cresc, n = _soma_e_crescimento(tab, 4)
            # ano-calendário: só empresas com os 4 trimestres do ano
            anos = tab.groupby(tab.index.year).sum(min_count=4)  # empresa sem os 4 trimestres do ano fica vazia
            anos = anos.loc[[a for a in anos.index if (tab.index.year == a).sum() == 4]]  # só anos completos
            anos.index = pd.to_datetime([f"{a}-12-31" for a in anos.index])
            soma_a, cresc_a, _ = _soma_e_crescimento(anos, 1)
        tri[chave], tri[f"{chave}_cresc"] = _pacote(soma / 1e6, 1), _pacote(cresc, 2)  # US$ milhões
        anual[chave], anual[f"{chave}_cresc"] = _pacote(soma_a / 1e6, 1), _pacote(cresc_a, 2)
        cobertura[chave] = _pacote(n, 0)

    # indicadores de 12 meses (soma sobre soma), por trimestre
    def ltm(campo, fin_ok=True):
        return pd.DataFrame({e["id"]: e["ltm"][campo].reindex(trimestres) for e in empresas
                             if campo in e["ltm"] and (fin_ok or not e["fin"])}, index=trimestres)

    lucro, receita, pl = ltm("lucro_liquido"), ltm("receita"), ltm("pl")
    ebit_nf, pl_nf, dl_nf, ebitda_nf, fcf_nf = (ltm(c, False) for c in ("ebit", "pl", "divida_liquida", "ebitda", "fcf"))

    def razao(num, den):
        comuns = num.notna() & den.notna()
        a, b = num.where(comuns).sum(axis=1, min_count=1), den.where(comuns).sum(axis=1, min_count=1)
        return (a / b).where(comuns.sum(axis=1) >= 50)

    indicadores = {
        "roe": _pacote(razao(lucro, pl) * 100, 2),
        "roic": _pacote(razao(ebit_nf * (1 - ALIQUOTA), pl_nf + dl_nf) * 100, 2),
        "dl_ebitda": _pacote(razao(dl_nf, ebitda_nf), 2),
        "margem_liquida": _pacote(razao(lucro, receita) * 100, 2),
    }

    # valor de mercado semanal (preço ajustado × ações ajustadas por desdobramento) e P/L com o lucro já conhecido na data
    # semanas cotadas pela maior parte das empresas (as datas semanais do Yahoo são as mesmas para todas)
    contagem = pd.Series([d for e in empresas for d in e["precos"].index if d >= INICIO]).value_counts()
    datas = pd.DatetimeIndex(sorted(contagem[contagem >= 300].index))
    mcap, mcap_nf, lucro_conhecido, fcf_conhecido = {}, {}, {}, {}
    for e in empresas:
        if e["precos"].empty or e["acoes"].empty or "lucro_liquido" not in e["ltm"]:
            continue
        p = e["precos"].reindex(datas)
        a = e["acoes"].reindex(e["acoes"].index.union(datas)).ffill().reindex(datas)  # última quantidade informada até a data
        mcap[e["id"]] = p * a
        conhecido = e["ltm"].copy()
        conhecido.index = conhecido.index + pd.Timedelta(days=DEFASAGEM_BALANCO)
        lucro_conhecido[e["id"]] = conhecido["lucro_liquido"].reindex(conhecido.index.union(datas)).ffill().reindex(datas)
        if not e["fin"] and "fcf" in conhecido:
            mcap_nf[e["id"]] = mcap[e["id"]]
            fcf_conhecido[e["id"]] = conhecido["fcf"].reindex(conhecido.index.union(datas)).ffill().reindex(datas)
    mc, lc = pd.DataFrame(mcap, index=datas), pd.DataFrame(lucro_conhecido, index=datas)
    pe = razao(mc, lc)
    fy = razao(pd.DataFrame(fcf_conhecido, index=datas), pd.DataFrame(mcap_nf, index=datas)) * 100
    validos = mc.notna().sum(axis=1)
    pe, fy = pe[validos >= 300], fy[validos >= 300]  # semanas com a maior parte do índice com preço e ações

    # cartões: situação atual (último trimestre com cobertura e último valor de mercado)
    resumo = json.loads((DIR_DADOS_SITE / "mundo_empresas.json").read_text(encoding="utf-8"))
    mercado = (json.loads((DIR_DADOS_SITE / "mundo.json").read_text(encoding="utf-8")).get("mercados") or {}).get("sp500")
    ult = lambda pac: pac["valores"][-1] if pac["valores"] else None  # noqa: E731
    cartoes = {
        "valor_mercado": sum(x.get("market_cap") or 0 for x in resumo["empresas"]),
        "pl": round(float(pe.dropna().iloc[-1]), 2) if pe.notna().any() else None,
        "fcf_yield": round(float(fy.dropna().iloc[-1]), 2) if fy.notna().any() else None,
        "roe": ult(indicadores["roe"]), "roic": ult(indicadores["roic"]), "dl_ebitda": ult(indicadores["dl_ebitda"]),
        "margem_liquida": ult(indicadores["margem_liquida"]),
        "n_empresas": len(resumo["empresas"]),
    }
    saida = {
        "gerado_em": datetime.now(FUSO_BR).isoformat(timespec="minutes"),
        "fonte": "Soma das empresas do índice — SEC EDGAR (balanços XBRL e ações), Yahoo Finance (cotações) e FRED (índice)",
        "trimestral": tri, "anual": anual, "indicadores": indicadores, "cobertura": cobertura,
        "pl_historico": _pacote(pe, 2), "fcf_yield": _pacote(fy, 2), "cotacao": mercado, "cartoes": cartoes,
        "descartados": descartados,
        "setores": {e["id"]: e["setor"] for e in empresas},
    }
    ARQ.write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    print(f"✅ S&P 500: {len(empresas)} empresas; P/L {cartoes['pl']}; ROE {cartoes['roe']}%; "
          f"último trimestre {tri['lucro']['datas'][-1] if tri['lucro']['datas'] else '—'}")
    return ARQ


if __name__ == "__main__":
    gerar()
