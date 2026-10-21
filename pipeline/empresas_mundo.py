"""
Mundo → Empresas: as empresas do S&P 500 com a mesma estrutura das empresas do Brasil.

- Universo: carteira diária do SPY (State Street SPDR S&P 500 ETF), arquivo público oficial do gestor
  (a lista do índice em si é paga). Pesos no índice vêm daí.
- Demonstrações: SEC EDGAR, API oficial "companyfacts" (dados XBRL que as empresas entregam nos 10-K e
  10-Q), convertidas para as mesmas séries das empresas brasileiras (receita, EBIT, lucro, caixa, dívida...)
  e para os mesmos indicadores (pipeline.series_empresa). Trimestres isolados por diferença dos acumulados
  do ano (o 4º tri = ano − 9 meses), anos pelos números do 10-K e LTM pela soma de 4 trimestres.
- Cadastro e documentos (8-K, 10-K, 10-Q): SEC EDGAR, API "submissions".
- Cotação: Yahoo Finance (não oficial), como o histórico de cotações das empresas brasileiras.

A SEC exige identificação em cada consulta: o texto vem do secret SEC_USER_AGENT (nunca fica no código).
Atualização: completa no fim de semana (ou sem histórico); nos outros dias, só as empresas que entregaram
documento novo à SEC (índice diário de documentos do EDGAR) e as cotações.

Saídas: site/dados/mundo_empresas.json (tabelão) e site/dados/mundo_empresas/{ticker}.json.
Uso: py -m pipeline.empresas_mundo [--tudo] [TICKER ...]
"""

import json
import math
import os
import sys
import time
from datetime import date, datetime, timedelta

import pandas as pd
import requests

from pipeline import DIR_DADOS_SITE, DIR_INTERMEDIARIO, sem_segredos
from pipeline.series_empresa import adicionar_indicadores, montar_visoes, para_json

URL_SPY = "https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx"
URL_TICKERS = "https://www.sec.gov/files/company_tickers_exchange.json"
URL_FATOS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
URL_SUBMISSOES = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
URL_INDICE_DIA = "https://www.sec.gov/Archives/edgar/daily-index/{ano}/QTR{tri}/form.{dia:%Y%m%d}.idx"
DIR_EMP = DIR_DADOS_SITE / "mundo_empresas"
ARQ_INDICE = DIR_DADOS_SITE / "mundo_empresas.json"
ARQ_REGISTRO = DIR_INTERMEDIARIO / "mundo_empresas_registro.json"
NAVEGADOR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"}
FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A", "10-KT", "10-QT"}
# Empresas que trocaram de registro na SEC (nova controladora): o histórico fica no CIK antigo e é somado ao novo
CIK_ANTERIOR = {"XOM": 34088}  # ExxonMobil Holdings Corp (2026) <- Exxon Mobil Corp
ANO_INICIAL = 2010


def _cab_sec():
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    if not ua:
        raise RuntimeError("SEC_USER_AGENT não configurado")
    return {"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}


def _get_sec(url, tentativas=4):
    """A SEC limita a 10 consultas por segundo: pausa curta entre consultas e nova tentativa se recusar."""
    for i in range(tentativas):
        try:
            r = requests.get(url, headers=_cab_sec(), timeout=90)
            if r.status_code == 404:
                return None
            if r.status_code in (403, 429, 503):
                raise requests.HTTPError(f"HTTP {r.status_code}")
            r.raise_for_status()
            time.sleep(0.12)
            return r
        except requests.RequestException as e:
            if i == tentativas - 1:
                status = getattr(getattr(e, "response", None), "status_code", None)
                raise RuntimeError(f"SEC: falha na consulta {url.split('/')[-1]}" + (f" (HTTP {status})" if status else f" ({e})")) from None
            time.sleep(2 * (i + 1))


# ---------------- universo ----------------
def universo():
    """Empresas da carteira do SPY (S&P 500) com o CIK da SEC."""
    import io
    r = requests.get(URL_SPY, headers=NAVEGADOR, timeout=90)
    r.raise_for_status()
    tab = pd.read_excel(io.BytesIO(r.content), header=4)
    tab = tab[tab["Ticker"].astype(str).str.match(r"^[A-Z][A-Z0-9.]*$") & (tab["Ticker"].astype(str) != "CASH_USD")]
    sec = _get_sec(URL_TICKERS).json()
    campos = sec["fields"]
    por_ticker = {}
    for linha in sec["data"]:
        x = dict(zip(campos, linha))
        por_ticker.setdefault(str(x["ticker"]).upper(), x)
    saida = []
    for _, l in tab.iterrows():
        t = str(l["Ticker"]).upper()
        x = por_ticker.get(t) or por_ticker.get(t.replace(".", "-"))
        if not x:
            continue
        saida.append({"ticker": t.replace(".", "-"), "nome_spy": str(l["Name"]).strip(), "cik": int(x["cik"]), "nome": x["name"],
                      "bolsa": x.get("exchange"), "peso": round(float(l["Weight"]), 4) if pd.notna(l["Weight"]) else None})
    # a mesma empresa pode ter duas classes (GOOGL/GOOG, FOX/FOXA): uma página por empresa, peso somado
    unicas = {}
    for e in saida:
        if e["cik"] in unicas:
            unicas[e["cik"]]["peso"] = round((unicas[e["cik"]]["peso"] or 0) + (e["peso"] or 0), 4)
            unicas[e["cik"]]["outras_classes"] = unicas[e["cik"]].get("outras_classes", []) + [e["ticker"]]
        else:
            unicas[e["cik"]] = e
    if len(unicas) < 450:
        raise RuntimeError(f"universo do S&P 500 com só {len(unicas)} empresas (layout do arquivo do SPY mudou?)")
    data_ref = None
    try:
        cab = pd.read_excel(io.BytesIO(r.content), header=None, nrows=3)
        data_ref = str(cab.iloc[2, 1]).replace("As of ", "")
    except Exception:  # noqa: BLE001
        pass
    return list(unicas.values()), data_ref


# ---------------- séries a partir do companyfacts ----------------
FLUXOS_GAAP = {
    "receita": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax",
                "SalesRevenueNet", "SalesRevenueGoodsNet", "RevenuesNetOfInterestExpense", "RevenueNet",
                "RegulatedAndUnregulatedOperatingRevenue", "ElectricUtilityRevenue", "OilAndGasRevenue"],
    # bancos: receita líquida = margem financeira líquida + receitas de serviços (quando não há conta de receita total)
    "margem_fin": ["InterestIncomeExpenseNet", "InterestIncomeExpenseAfterProvisionForLoanLoss"],
    "receita_servicos": ["NoninterestIncome"],
    "custo": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold", "CostOfServices", "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization"],
    "lucro_bruto": ["GrossProfit"],
    "sga": ["SellingGeneralAndAdministrativeExpense", "GeneralAndAdministrativeExpense"],
    "pd": ["ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"],
    "ebit": ["OperatingIncomeLoss"],
    "lair": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
             "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],
    "ir_despesa": ["IncomeTaxExpenseBenefit"],
    "lucro_liquido": ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic", "ProfitLoss"],
    "rec_fin": ["InvestmentIncomeInterest", "InvestmentIncomeInterestAndDividend"],
    "desp_juros": ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"],
    "fco": ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "fci": ["NetCashProvidedByUsedInInvestingActivities", "NetCashProvidedByUsedInInvestingActivitiesContinuingOperations"],
    "fcfin": ["NetCashProvidedByUsedInFinancingActivities", "NetCashProvidedByUsedInFinancingActivitiesContinuingOperations"],
    "var_caixa": ["CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
                  "CashAndCashEquivalentsPeriodIncreaseDecrease"],
    "da": ["DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet", "DepreciationAndAmortization",
           "DepreciationAmortizationAndOther"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "div_pagos": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
    "recompras": ["PaymentsForRepurchaseOfCommonStock"],
}
SALDOS_GAAP = {
    "ativo_total": ["Assets"], "ativo_circ": ["AssetsCurrent"],
    "caixa": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "Cash"],
    "aplicacoes": ["ShortTermInvestments", "MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesDebtSecuritiesCurrent"],
    "recebiveis": ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"], "estoques": ["InventoryNet"],
    "imobilizado": ["PropertyPlantAndEquipmentNet", "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization"],
    "goodwill": ["Goodwill"], "intangiveis": ["IntangibleAssetsNetExcludingGoodwill", "FiniteLivedIntangibleAssetsNet"],
    "passivo_total": ["Liabilities"], "passivo_circ": ["LiabilitiesCurrent"], "fornecedores": ["AccountsPayableCurrent"],
    "divida_cp": ["DebtCurrent", "LongTermDebtCurrent"], "papeis_cp": ["ShortTermBorrowings", "CommercialPaper"],
    "emprest_lp": ["LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations", "LongTermDebt"],
    "arrendamentos": ["OperatingLeaseLiability"],
    "pl": ["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", "StockholdersEquity"],
    "pl_controladores": ["StockholdersEquity"], "minoritarios": ["MinorityInterest"],
    "passivo_pl": ["LiabilitiesAndStockholdersEquity"],
}


# Meses em que terminam os trimestres fiscais da empresa em processamento (definido em montar_empresa)
_MESES_TRIMESTRE = None


def _fim_normalizado(iso):
    """
    Fim de trimestre de 52/53 semanas (27/12, 06/09, 01/02...) -> último dia do mês de fechamento do trimestre fiscal:
    o fim de mês mais próximo entre os 4 meses de fechamento da empresa (ex.: exercício em dezembro -> mar, jun, set, dez).
    Sem o calendário da empresa, usa o fim de mês uma semana antes.
    """
    d = pd.Timestamp(iso)
    if _MESES_TRIMESTRE:
        candidatos = [pd.Timestamp(a, m, 1) + pd.offsets.MonthEnd(0) for a in (d.year - 1, d.year, d.year + 1) for m in _MESES_TRIMESTRE]
        return min(candidatos, key=lambda c: abs((c - d).days)).date()
    return (d - pd.Timedelta(days=7) + pd.offsets.MonthEnd(0)).date()


def _mes_fim_exercicio(gaap):
    """Mês de fechamento do exercício: fim de mês mais próximo das datas dos anos (350–380 dias) do 10-K."""
    fins = []
    for c in ("NetIncomeLoss", "ProfitLoss", "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "Assets"):
        for f in (gaap.get(c, {}).get("units", {}).get("USD") or []):
            if f.get("form") == "10-K" and f.get("start") and 350 <= (pd.Timestamp(f["end"]) - pd.Timestamp(f["start"])).days + 1 <= 380:
                d = pd.Timestamp(f["end"])
                fins.append(min((d + pd.offsets.MonthEnd(0), d - pd.offsets.MonthEnd(1)), key=lambda c: abs((c - d).days)).month)
        if fins:
            break
    return max(set(fins[-12:]), key=fins[-12:].count) if fins else 12


def _fatos(gaap, conceitos, unidade="USD"):
    """Fatos dos conceitos (em ordem de prioridade), um por (início, fim): o primeiro conceito que tiver o período, envio mais recente."""
    por_periodo = {}
    for prio, c in enumerate(conceitos):
        for f in (gaap.get(c, {}).get("units", {}).get(unidade) or []):
            if f.get("form") not in FORMS:
                continue
            chave = (f.get("start"), f["end"])
            atual = por_periodo.get(chave)
            if atual is None or (prio, -int(f["filed"].replace("-", ""))) < (atual[0], -int(atual[1]["filed"].replace("-", ""))):
                por_periodo[chave] = (prio, f)
    return [f for _, f in por_periodo.values()]


def _fluxo(gaap, conceitos):
    """(trimestres isolados {fim: valor}, anos {fim: valor}) a partir dos acumulados do ano."""
    fatos = [f for f in _fatos(gaap, conceitos) if f.get("start")]
    tri, anos, por_inicio = {}, {}, {}
    for f in fatos:
        ini, fim = pd.Timestamp(f["start"]), pd.Timestamp(f["end"])
        dias = (fim - ini).days + 1
        if 77 <= dias <= 125:  # trimestres de 12 a 17 semanas (varejistas têm um trimestre de 16 semanas)
            tri[f["end"]] = float(f["val"])
        if 350 <= dias <= 380:
            anos[f["end"]] = float(f["val"])
        if 77 <= dias <= 380:
            por_inicio.setdefault(f["start"], []).append((fim, dias, float(f["val"])))
    # trimestre que falta = acumulado − acumulado anterior com o mesmo início (ex.: 4º tri = ano − 9 meses)
    for ini, lista in por_inicio.items():
        lista.sort()
        for (f0, d0, v0), (f1, d1, v1) in zip(lista, lista[1:]):
            if 77 <= d1 - d0 <= 125 and f1.strftime("%Y-%m-%d") not in tri:
                tri[f1.strftime("%Y-%m-%d")] = v1 - v0
    norm = lambda m: {_fim_normalizado(k): v for k, v in sorted(m.items())}  # noqa: E731
    return norm(tri), norm(anos)


def _saldo(gaap, conceitos):
    return {_fim_normalizado(f["end"]): float(f["val"]) for f in sorted(_fatos(gaap, conceitos), key=lambda f: f["end"]) if not f.get("start")}


def _juntar_fatos(antigo, novo):
    """Soma os fatos de dois registros (o novo prevalece no mesmo período, pela data de envio mais recente)."""
    saida = {"facts": {}}
    for tax in set(antigo.get("facts", {})) | set(novo.get("facts", {})):
        a, n = antigo["facts"].get(tax, {}), novo.get("facts", {}).get(tax, {})
        saida["facts"][tax] = {}
        for c in set(a) | set(n):
            unidades = {}
            for fonte in (a.get(c, {}), n.get(c, {})):
                for un, lista in (fonte.get("units") or {}).items():
                    unidades.setdefault(un, []).extend(lista)
            saida["facts"][tax][c] = {"units": unidades}
    return saida


def montar_empresa(fatos):
    global _MESES_TRIMESTRE
    gaap = fatos.get("facts", {}).get("us-gaap", {})
    if not gaap:
        return None
    mes_fim = _mes_fim_exercicio(gaap)
    _MESES_TRIMESTRE = sorted({(mes_fim - 1 - 3 * k) % 12 + 1 for k in range(4)})
    tri, anos = {}, {}
    for k, conc in FLUXOS_GAAP.items():
        tri[k], anos[k] = _fluxo(gaap, conc)
    saldos = {k: _saldo(gaap, conc) for k, conc in SALDOS_GAAP.items()}
    datas = sorted(d for d in set().union(*[set(v) for v in tri.values()]) if d.year >= ANO_INICIAL)
    datas = [d for d in datas if tri["receita"].get(d) is not None or tri["lucro_liquido"].get(d) is not None]
    if len(datas) < 4:
        return None
    q = pd.DataFrame(index=datas)
    for k in tri:
        q[k] = [tri[k].get(d, float("nan")) for d in datas]
    for k in saldos:
        q[k] = [saldos[k].get(d, float("nan")) for d in datas]
    # convenções das empresas brasileiras: despesas e IR negativos; dívida = empréstimos de curto + longo prazo
    q["receita"] = q["receita"].fillna(q["margem_fin"] + q["receita_servicos"])
    q["lucro_bruto"] = q["lucro_bruto"].fillna(q["receita"] - q["custo"])
    q["ir"] = -q["ir_despesa"]
    q["desp_fin"] = -q["desp_juros"]
    q["res_fin"] = q["lair"] - q["ebit"]
    for k in ("da", "capex", "div_pagos", "recompras"):
        q[k] = q[k].abs()
    q["emprest_cp"] = q["divida_cp"].fillna(0) + q["papeis_cp"].fillna(0)
    q.loc[q["divida_cp"].isna() & q["papeis_cp"].isna(), "emprest_cp"] = float("nan")
    q["ebitda"] = q["ebit"] + q["da"].fillna(0)
    q["fcf"] = q["fco"] - q["capex"].fillna(0)
    emprest = q[["emprest_cp", "emprest_lp"]].sum(axis=1, min_count=1)
    caixa_total = q["caixa"].fillna(0) + q["aplicacoes"].fillna(0)
    q["divida_bruta"] = emprest
    q["divida_bruta_ifrs16"] = emprest.fillna(0) + q["arrendamentos"].fillna(0)
    q["divida_liquida"] = q["divida_bruta"].fillna(0) - caixa_total
    q["divida_liquida_ifrs16"] = q["divida_bruta_ifrs16"] - caixa_total
    # aplicações financeiras que somem de um trimestre para o outro (a empresa trocou a etiqueta XBRL por uma própria):
    # a dívida líquida daquele trimestre ficaria superestimada, então fica em branco
    sumiu = q["aplicacoes"].isna() & q["aplicacoes"].shift(1).notna() | (q["aplicacoes"].isna() & q["aplicacoes"].ffill().notna())
    q.loc[sumiu, ["divida_liquida", "divida_liquida_ifrs16"]] = float("nan")
    q = q.sort_index()
    # trimestres de 16 semanas: o fim de um trimestre pode ficar até ~4 meses depois do anterior
    import pipeline.series_empresa as se
    original = se._consecutivos
    se._consecutivos = lambda datas: all(70 <= (b - a).days <= 130 for a, b in zip(datas, datas[1:]))
    try:
        visoes = montar_visoes(q, mes_fim)
    finally:
        se._consecutivos = original  # o Brasil (mesmo processo) continua com a regra original
    # anos: número do 10-K quando existir (como a DFP no Brasil)
    a = visoes["anual"]
    for k in ("receita", "lucro_bruto", "ebit", "lair", "lucro_liquido", "fco", "fci", "fcfin", "da", "capex", "div_pagos"):
        for d in a.index:
            v = anos[k].get(d) if k in anos else None
            if v is not None and not math.isnan(v):
                a.loc[d, k] = abs(v) if k in ("da", "capex", "div_pagos") else v
    visoes = adicionar_indicadores(visoes, aliquota=0.21)
    return q, visoes, mes_fim, tri, anos, saldos


# DRE e balanço no formato da aba Resultados (mesmos códigos usados nas empresas brasileiras)
LINHAS_DRE = [("3.01", "Receita líquida", "receita"), ("3.02", "Custo dos produtos e serviços", "custo_neg"), ("3.03", "Lucro bruto", "lucro_bruto"),
              ("3.04", "Despesas operacionais", "despesas"), ("3.05", "EBIT (resultado operacional)", "ebit"), ("3.06", "Resultado financeiro e outros", "res_fin"),
              ("3.07", "Lucro antes do IR", "lair"), ("3.08", "IR e contribuições", "ir"), ("3.11", "Lucro líquido", "lucro_liquido")]
LINHAS_BP = [("1", "Ativo total", "ativo_total"), ("1.01", "Ativo circulante", "ativo_circ"), ("1.01.01", "Caixa e equivalentes", "caixa"),
             ("1.01.02", "Aplicações financeiras", "aplicacoes"), ("1.01.03", "Contas a receber", "recebiveis"), ("1.01.04", "Estoques", "estoques"),
             ("1.02", "Ativo não circulante", "ativo_nc"), ("1.02.03", "Imobilizado", "imobilizado"), ("1.02.04", "Goodwill", "goodwill"),
             ("1.02.05", "Intangíveis", "intangiveis"), ("2", "Passivo total + patrimônio líquido", "passivo_pl"), ("2.01", "Passivo circulante", "passivo_circ"),
             ("2.01.02", "Fornecedores", "fornecedores"), ("2.01.04", "Empréstimos e financiamentos (CP)", "emprest_cp"),
             ("2.02", "Passivo não circulante", "passivo_nc"), ("2.02.01", "Empréstimos e financiamentos (LP)", "emprest_lp"),
             ("2.02.02", "Arrendamentos operacionais", "arrendamentos"), ("2.03", "Patrimônio líquido consolidado", "pl"),
             ("2.03.01", "Patrimônio dos controladores", "pl_controladores"), ("2.03.09", "Participação de não controladores", "minoritarios")]


def demonstracoes(q, visoes, anos_fluxo, n_anos=4):
    anual, ltm = visoes["anual"], visoes["ltm"]
    colunas = [(d, False) for d in list(anual.index)[-n_anos:]]
    if not ltm.empty and (not colunas or ltm.index[-1] != colunas[-1][0]):
        colunas.append((ltm.index[-1], True))
    if not colunas:
        return None

    def fluxo(k, d, e_ltm):
        v = (ltm if e_ltm else anual)
        if k == "custo_neg":
            x = v.loc[d, "receita"] - v.loc[d, "lucro_bruto"] if not (pd.isna(v.loc[d, "receita"]) or pd.isna(v.loc[d, "lucro_bruto"])) else float("nan")
            return -x if not pd.isna(x) else x
        if k == "despesas":
            return v.loc[d, "ebit"] - v.loc[d, "lucro_bruto"]
        return v.loc[d, k] if k in v.columns else float("nan")

    def saldo(k, d):
        if d not in q.index:
            return float("nan")
        if k == "ativo_nc":
            return q.loc[d, "ativo_total"] - q.loc[d, "ativo_circ"]
        if k == "passivo_nc":
            pt = q.loc[d, "passivo_total"]
            if pd.isna(pt):
                pt = q.loc[d, "passivo_pl"] - q.loc[d, "pl"]
            return pt - q.loc[d, "passivo_circ"]
        if k == "passivo_pl" and pd.isna(q.loc[d, k]):
            return q.loc[d, "ativo_total"]
        return q.loc[d, k] if k in q.columns else float("nan")

    def limpo(x):
        return None if x is None or pd.isna(x) else round(float(x), 2)

    dre = [{"c": c, "r": r, "v": [limpo(fluxo(k, d, l)) for d, l in colunas]} for c, r, k in LINHAS_DRE]
    bp = [{"c": c, "r": r, "v": [limpo(saldo(k, d)) for d, l in colunas]} for c, r, k in LINHAS_BP]
    bp = [x for x in bp if any(v not in (None, 0) for v in x["v"])]
    return {"colunas": [{"data": d.isoformat(), "ltm": l} for d, l in colunas], "dre": [x for x in dre if any(v is not None for v in x["v"])], "bp": bp}


# ---------------- cadastro e documentos ----------------
ITENS_8K = {"1.01": "Contrato relevante", "1.02": "Fim de contrato relevante", "1.03": "Falência ou recuperação", "2.01": "Aquisição ou venda de ativos",
            "2.02": "Resultado do período", "2.03": "Nova dívida", "2.05": "Reestruturação", "2.06": "Baixa contábil (impairment)",
            "3.01": "Listagem em bolsa", "3.02": "Venda de ações não registrada", "4.01": "Troca de auditor", "4.02": "Republicação de demonstrações",
            "5.01": "Mudança de controle", "5.02": "Diretores e conselheiros (entrada/saída)", "5.03": "Estatuto", "5.07": "Votação de acionistas",
            "7.01": "Divulgação ao mercado (Reg FD)", "8.01": "Outros eventos", "9.01": "Demonstrações e anexos"}


def cadastro_e_documentos(cik):
    r = _get_sec(URL_SUBMISSOES.format(cik=cik))
    if r is None:
        return {}, []
    s = r.json()
    cad = {"setor": s.get("sicDescription"), "sic": s.get("sic"), "estado": s.get("stateOfIncorporation"), "exercicio_termina": s.get("fiscalYearEnd"),
           "tickers": s.get("tickers"), "bolsas": s.get("exchanges"), "categoria": s.get("category"),
           "sede": ", ".join(x for x in [(s.get("addresses", {}).get("business") or {}).get("city"), (s.get("addresses", {}).get("business") or {}).get("stateOrCountry")] if x)}
    rec = s.get("filings", {}).get("recent", {})
    docs, limite = [], (date.today() - timedelta(days=3 * 365)).isoformat()
    for i, form in enumerate(rec.get("form", [])):
        if form not in ("8-K", "10-K", "10-Q", "10-K/A", "DEF 14A", "8-K/A") or rec["filingDate"][i] < limite:
            continue
        acc = rec["accessionNumber"][i].replace("-", "")
        itens = [x.strip() for x in (rec.get("items", [""] * (i + 1))[i] or "").split(",") if x.strip()]
        descr = "; ".join(ITENS_8K.get(x, x) for x in itens if x != "9.01") if form.startswith("8-K") else \
            {"10-K": "Relatório anual (10-K)", "10-Q": "Relatório trimestral (10-Q)", "10-K/A": "Relatório anual — correção",
             "DEF 14A": "Convocação da assembleia (proxy)"}.get(form, form)
        docs.append({"data": rec["filingDate"][i], "tipo": form, "assunto": descr or "Comunicado (8-K)",
                     "link": f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{rec['primaryDocument'][i]}",
                     "relevante": form.startswith("8-K") and any(x in ("1.01", "2.01", "2.02", "2.05", "2.06", "4.02", "5.01", "8.01") for x in itens)})
    ultimo_10k = next(({"data": d["data"], "link": d["link"]} for d in docs if d["tipo"] == "10-K"), None)
    cad["ultimo_10k"] = ultimo_10k
    return cad, docs[:200]


# ---------------- demonstrações como divulgadas à SEC ----------------
# A SEC monta, de cada 10-K/10-Q, as tabelas das demonstrações (R2.htm, R3.htm...) com as linhas, os nomes (em inglês)
# e a granularidade que a própria empresa divulgou. São usadas como estão, sem reclassificar contas.
TIPOS_DEMONSTRACAO = [
    ("dre", ("STATEMENTS OF OPERATIONS", "STATEMENT OF OPERATIONS", "STATEMENTS OF INCOME", "STATEMENT OF INCOME", "STATEMENTS OF EARNINGS",
             "STATEMENT OF EARNINGS", "INCOME STATEMENTS", "INCOME STATEMENT", "STATEMENTS OF CONSOLIDATED INCOME", "STATEMENTS OF CONSOLIDATED OPERATIONS",
             "RESULTS OF OPERATIONS")),
    ("balanco", ("BALANCE SHEET", "FINANCIAL CONDITION", "FINANCIAL POSITION", "STATEMENTS OF CONDITION")),
    ("caixa", ("CASH FLOW",)),
]


def _numero(txt):
    if txt is None or (isinstance(txt, float) and math.isnan(txt)):
        return None
    t = str(txt).replace("$", "").replace(",", "").replace(" ", " ").strip()
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").strip()
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def _tabela_r(url):
    import io
    r = _get_sec(url)
    if r is None:
        return None
    tabs = pd.read_html(io.StringIO(r.text))
    if not tabs:
        return None
    t = tabs[0]
    cols = list(t.columns)
    titulo = cols[0][0] if isinstance(cols[0], tuple) else str(cols[0])
    rotulos = [" ".join(x for x in (c if isinstance(c, tuple) else (c,)) if x and "Unnamed" not in str(x) and x != titulo).strip() for c in cols[1:]]
    linhas = []
    for _, l in t.iterrows():
        nome = str(l.iloc[0]).strip()
        if not nome or nome == "nan" or nome.startswith("["):
            continue
        vals = [_numero(x) for x in l.iloc[1:]]
        linhas.append({"r": nome, "v": vals, "secao": all(v is None for v in vals)})
    # colunas sem nenhum número (a SEC às vezes repete a coluna de rótulos) saem da tabela
    manter = [i for i in range(len(rotulos)) if any(l["v"][i] is not None for l in linhas)]
    rotulos = [rotulos[i] for i in manter]
    for l in linhas:
        l["v"] = [l["v"][i] for i in manter]
    unidade = titulo.split(" - ", 1)[1] if " - " in titulo else ""
    return {"titulo": titulo.split(" - ")[0].strip().title(), "unidade": unidade.strip(), "colunas": rotulos, "linhas": linhas}


def demonstracoes_sec(docs):
    """DRE, balanço e fluxo de caixa do último 10-K e do último 10-Q (se mais recente), como divulgados."""
    import re
    saida = {}
    k = next((d for d in docs if d["tipo"] == "10-K"), None)
    qd = next((d for d in docs if d["tipo"] == "10-Q"), None)
    for nome, doc in (("anual", k), ("trimestral", qd if qd and (not k or qd["data"] > k["data"]) else None)):
        if not doc:
            continue
        base = doc["link"].rsplit("/", 1)[0]
        fs = _get_sec(base + "/FilingSummary.xml")
        if fs is None:
            continue
        relatorios = []
        for bloco in re.findall(r"<Report instance=.*?</Report>", fs.text, re.S):
            cat = re.search(r"<MenuCategory>(.*?)</MenuCategory>", bloco)
            nm = re.search(r"<ShortName>(.*?)</ShortName>", bloco)
            arq = re.search(r"<HtmlFileName>(.*?)</HtmlFileName>", bloco)
            if cat and cat.group(1) == "Statements" and nm and arq:
                relatorios.append((nm.group(1).upper(), arq.group(1)))
        tabelas = {}
        for chave, padroes in TIPOS_DEMONSTRACAO:
            escolhido = next((a for n, a in relatorios if any(p in n for p in padroes) and "PARENTHETICAL" not in n
                              and "COMPREHENSIVE" not in n.replace("AND COMPREHENSIVE", "")), None)
            if escolhido:
                try:
                    tab = _tabela_r(f"{base}/{escolhido}")
                    if tab and tab["linhas"]:
                        tabelas[chave] = tab
                except Exception:  # noqa: BLE001
                    pass
        if tabelas:
            saida[nome] = {"documento": doc["tipo"], "data": doc["data"], "link": doc["link"], **tabelas}
    return saida


# ---------------- cotações (Yahoo, não oficial) ----------------
def cotacoes(tickers, semanal=False):
    import yfinance as yf
    yt = [t.replace(".", "-") for t in tickers]
    dados = yf.download(yt, period="10y" if semanal else "1y", interval="1wk" if semanal else "1d", auto_adjust=False,
                        progress=False, group_by="column", threads=True)
    fech = dados["Close"] if "Close" in dados else pd.DataFrame()
    return fech


# ---------------- índice diário do EDGAR: quem entregou documento ----------------
def ciks_com_documento_desde(desde):
    ciks, d = {}, desde
    while d <= date.today():
        if d.weekday() < 5:
            try:  # o índice do dia só sai à noite (antes disso a SEC responde 403)
                r = _get_sec(URL_INDICE_DIA.format(ano=d.year, tri=(d.month - 1) // 3 + 1, dia=d), tentativas=1)
            except RuntimeError:
                r = None
            if r is not None:
                for linha in r.text.splitlines():
                    partes = linha.split()
                    if len(partes) >= 5 and partes[0] in FORMS | {"8-K", "8-K/A"} and partes[-3].isdigit():
                        ciks[int(partes[-3])] = partes[0]
        d += timedelta(days=1)
    return ciks


def _sem_nan(x):
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x


def gerar(tudo=False, filtro=None):
    DIR_EMP.mkdir(parents=True, exist_ok=True)
    registro = json.loads(ARQ_REGISTRO.read_text(encoding="utf-8")) if ARQ_REGISTRO.exists() else {}
    empresas, data_spy = universo()
    hoje = date.today()
    semanal = hoje.weekday() >= 5 and registro.get("_semanal") != hoje.isocalendar()[:2].__repr__()
    # o próprio código mudou (nova regra de leitura do XBRL): refaz todas as empresas, como no Brasil
    import hashlib
    versao = hashlib.sha256(open(__file__, "rb").read() + open(__file__.replace("empresas_mundo.py", "series_empresa.py"), "rb").read()).hexdigest()[:16]
    codigo_mudou = registro.get("_versao") != versao
    if filtro:
        alvo = {e["cik"] for e in empresas if e["ticker"] in filtro}
    elif tudo or semanal or codigo_mudou or not registro.get("_ultimo_indice"):
        alvo = {e["cik"] for e in empresas}
    else:
        desde = date.fromisoformat(registro["_ultimo_indice"]) - timedelta(days=1)
        alvo = set(ciks_com_documento_desde(desde)) & {e["cik"] for e in empresas}
        alvo |= {e["cik"] for e in empresas if e["ticker"] not in registro}  # entraram no índice
    print(f"   S&P 500: {len(empresas)} empresas (SPY de {data_spy}); a processar: {len(alvo)}")

    falhas = []
    for i, e in enumerate(empresas, 1):
        if e["cik"] not in alvo:
            continue
        try:
            fatos = _get_sec(URL_FATOS.format(cik=e["cik"]))
            fj = fatos.json() if fatos is not None else {"facts": {}}
            if e["ticker"] in CIK_ANTERIOR:
                antigo = _get_sec(URL_FATOS.format(cik=CIK_ANTERIOR[e["ticker"]]))
                if antigo is not None:
                    fj = _juntar_fatos(antigo.json(), fj)
            montado = montar_empresa(fj) if fj.get("facts") else None
            if not montado:
                raise RuntimeError("sem demonstrações suficientes no XBRL")
            q, visoes, mes_fim, tri, anos, saldos = montado
            cad, docs = cadastro_e_documentos(e["cik"])
            if e["ticker"] in CIK_ANTERIOR:  # documentos do registro antigo (ex.: último 10-K antes da reorganização)
                _, docs_ant = cadastro_e_documentos(CIK_ANTERIOR[e["ticker"]])
                docs = sorted(docs + docs_ant, key=lambda x: x["data"], reverse=True)[:200]
            try:
                demons_sec = demonstracoes_sec(docs)
            except Exception as ex:  # noqa: BLE001
                demons_sec = {}
                falhas.append(sem_segredos(f"{e['ticker']}: demonstrações da SEC — {ex}")[:200])
            # ações em circulação (capa do 10-K/10-Q) e lucro por ação
            dei = fj.get("facts", {}).get("dei", {})
            acoes = sorted((dei.get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares") or []), key=lambda f: (f["end"], f["filed"]))
            gaap = fj["facts"]["us-gaap"]
            dps_t, dps_a = _fluxo(gaap, ["CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"]) if any(
                c in gaap for c in ("CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid")) else ({}, {})
            dps_unid = {}
            for c in ("CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"):
                for f in (gaap.get(c, {}).get("units", {}).get("USD/shares") or []):
                    if f.get("start") and 350 <= (pd.Timestamp(f["end"]) - pd.Timestamp(f["start"])).days + 1 <= 380:
                        dps_unid[_fim_normalizado(f["end"]).isoformat()] = float(f["val"])
            dados = {
                "id": e["ticker"], "nome": e["nome"], "cnpj": f"CIK {e['cik']}", "cik": e["cik"], "tickers": [e["ticker"], *e.get("outras_classes", [])],
                "setor": cad.get("setor"), "unidade": "US$", "moeda": "US$", "mes_fim_exercicio": mes_fim, "gerado_em": hoje.isoformat(),
                "cadastro": cad, "documentos": docs, "peso_sp500": e["peso"],
                "acoes": acoes[-1]["val"] if acoes else None, "acoes_data": acoes[-1]["end"] if acoes else None,
                "dividendo_por_acao_ano": dps_unid,
                "notas": {"fonte": "SEC EDGAR — companyfacts (XBRL dos 10-K e 10-Q)"},
                **para_json(visoes),
                "demonstracoes_sec": demons_sec,
            }
            (DIR_EMP / f"{e['ticker']}.json").write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":"), default=_sem_nan), encoding="utf-8")
            registro[e["ticker"]] = {"cik": e["cik"], "gerado": hoje.isoformat()}
        except Exception as ex:  # noqa: BLE001
            falhas.append(sem_segredos(f"{e['ticker']}: {ex}")[:200])
        if i % 50 == 0:
            print(f"   {i}/{len(empresas)}")

    # histórico semanal de cotações: no fim de semana, na carga completa e quando falta em alguma empresa
    falta_historico = any(not (DIR_EMP / f"{e['ticker']}.json").exists() or '"cotacao_semanal"' not in (DIR_EMP / f"{e['ticker']}.json").read_text(encoding="utf-8")
                          for e in empresas[:20])
    gerar_indice(empresas, data_spy, semanal or tudo or len(alvo) >= len(empresas) // 2 or falta_historico)
    registro["_ultimo_indice"] = hoje.isoformat()
    if not filtro:
        registro["_versao"] = versao
    if semanal:
        registro["_semanal"] = hoje.isocalendar()[:2].__repr__()
    ARQ_REGISTRO.write_text(json.dumps(registro, ensure_ascii=False), encoding="utf-8")
    print(f"✅ empresas do Mundo: {len(alvo)} processadas; {len(falhas)} falhas")
    for f in falhas[:30]:
        print("   ⚠️", f)
    if len(falhas) > max(25, len(alvo) // 5):
        raise RuntimeError(f"muitas falhas nas empresas do Mundo ({len(falhas)})")
    return falhas


def gerar_indice(empresas, data_spy, com_historico):
    """Tabelão: indicadores LTM de cada empresa + cotação do dia (Yahoo) e valor de mercado."""
    linhas, tickers = [], [e["ticker"] for e in empresas]
    try:
        fech = cotacoes(tickers)
    except Exception as ex:  # noqa: BLE001
        print("   ⚠️ cotações:", ex)
        fech = pd.DataFrame()
    semanais = None
    if com_historico:
        try:
            semanais = cotacoes(tickers, semanal=True)
        except Exception as ex:  # noqa: BLE001
            print("   ⚠️ cotações semanais:", ex)
    for e in empresas:
        arq = DIR_EMP / f"{e['ticker']}.json"
        if not arq.exists():
            continue
        d = json.loads(arq.read_text(encoding="utf-8"))
        L, n = d["ltm"]["series"], len(d["ltm"]["periodos"]) - 1
        g = lambda k: (L.get(k) or [None])[n] if n >= 0 else None  # noqa: E731
        preco = var = var12 = data_preco = None
        if e["ticker"] in fech.columns:
            s = fech[e["ticker"]].dropna()
            if len(s):
                preco, data_preco = float(s.iloc[-1]), s.index[-1].strftime("%Y-%m-%d")
                var = float(s.iloc[-1] / s.iloc[-2] - 1) if len(s) > 1 else None
                var12 = float(s.iloc[-1] / s.iloc[0] - 1) if len(s) > 200 else None
        mcap = preco * d["acoes"] if preco and d.get("acoes") else None
        ev = mcap + (g("divida_liquida") or 0) if mcap else None
        cot = {"preco": preco, "variacao_dia": var * 100 if var is not None else None, "data": data_preco}
        if semanais is not None and e["ticker"] in semanais.columns:
            s = semanais[e["ticker"]].dropna()
            d["cotacao_semanal"] = {"datas": [x.strftime("%Y-%m-%d") for x in s.index], "fechamento": [round(float(v), 2) for v in s]}
        d["cotacao"] = cot
        d["market_cap"] = mcap
        arq.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":"), default=_sem_nan), encoding="utf-8")
        pos = lambda v: v if v and v > 0 else None  # noqa: E731
        linhas.append({
            "id": e["ticker"], "nome": d["nome"], "setor": d.get("setor"), "peso": e["peso"], "preco": preco, "var_dia": cot["variacao_dia"],
            "var_12m": var12 * 100 if var12 is not None else None,
            "market_cap": mcap, "receita": g("receita"), "ebitda": g("ebitda"), "lucro": g("lucro_liquido"),
            "m_ebit": g("m_ebit"), "m_liquida": g("m_liquida"), "roe": g("roe"), "roic": g("roic"), "dl_ebitda": g("dl_ebitda"),
            "pl_x": mcap / g("lucro_liquido") if mcap and pos(g("lucro_liquido")) else None,
            "pvp": mcap / g("pl") if mcap and pos(g("pl")) else None,
            "ev_ebitda": ev / g("ebitda") if ev and pos(g("ebitda")) else None,
            "dy": (g("div_pagos") or 0) / mcap if mcap else None,
            "ultimo": d["ltm"]["periodos"][-1] if d["ltm"]["periodos"] else None,
        })
    ARQ_INDICE.write_text(json.dumps({"gerado_em": date.today().isoformat(), "spy_em": data_spy, "empresas": sorted(linhas, key=lambda x: -(x["peso"] or 0))},
                                     ensure_ascii=False, separators=(",", ":"), default=_sem_nan), encoding="utf-8")


if __name__ == "__main__":
    args = [a.upper() for a in sys.argv[1:] if not a.startswith("--")]
    gerar(tudo="--tudo" in sys.argv, filtro=set(args) or None)
