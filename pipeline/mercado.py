"""
Dados de mercado e proventos das empresas selecionadas:
- B3 (oficial): cotação atual por ticker, quantidade de ações ON/PN e proventos
  anunciados (a API devolve só ~12 meses);
- Yahoo Finance (gratuito, não oficial): histórico de proventos por ação e de
  cotação semanal, para os gráficos de vários anos.

Saídas: site/dados/mercado.json (resumo de todas), site/dados/proventos/{id}.json
"""

import base64
import json
import time
from datetime import date, datetime

import pandas as pd
import requests

from pipeline import DIR_DADOS_SITE
from src.screening import universo_selecionado

URL_EMPRESA = "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/GetListedSupplementCompany/{}"
URL_COTACAO = "https://cotacao.b3.com.br/mds/api/v1/instrumentQuotation/{}"
CABECALHO = {"User-Agent": "Mozilla/5.0"}
DIR_PROVENTOS = DIR_DADOS_SITE / "proventos"
CLASSE_POR_ISIN = {"ACNOR": "ON", "ACNPR": "PN", "ACNPA": "PNA", "ACNPB": "PNB", "CDAM": "UNIT"}


def _get_json(url, tentativas=3):
    for i in range(tentativas):
        try:
            r = requests.get(url, headers=CABECALHO, timeout=30)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError):
            if i == tentativas - 1:
                return None
            time.sleep(2 * (i + 1))


def _num_br(texto):
    if texto in (None, ""):
        return None
    return float(str(texto).replace(".", "").replace(",", "."))


def _data_br(texto):
    try:
        return datetime.strptime(texto, "%d/%m/%Y").date().isoformat()
    except (TypeError, ValueError):
        return None


def dados_b3_empresa(codigo_emissor):
    params = base64.b64encode(json.dumps({"issuingCompany": codigo_emissor, "language": "pt-br"}).encode()).decode()
    dados = _get_json(URL_EMPRESA.format(params))
    if not dados:
        return None
    d = dados[0]
    proventos = []
    for p in d.get("cashDividends") or []:
        isin = p.get("isinCode") or ""
        classe = next((c for prefixo, c in CLASSE_POR_ISIN.items() if isin[6:].startswith(prefixo)), isin[6:11])
        proventos.append({
            "tipo": "JCP" if "JRS" in (p.get("label") or "").upper() else (p.get("label") or "").title(),
            "classe": classe, "isin": isin, "valor": _num_br(p.get("rate")),
            "data_com": _data_br(p.get("lastDatePrior")), "pagamento": _data_br(p.get("paymentDate")),
            "aprovado": _data_br(p.get("approvedOn")), "referente": p.get("relatedTo") or None,
        })
    return {
        "acoes_on": _num_br(d.get("numberCommonShares")) or 0,
        "acoes_pn": _num_br(d.get("numberPreferredShares")) or 0,
        "segmento": d.get("segment"),
        "proventos": sorted(proventos, key=lambda p: p["data_com"] or "", reverse=True),
    }


def cotacao_b3(ticker):
    dados = _get_json(URL_COTACAO.format(ticker))
    try:
        papel = dados["Trad"][0]["scty"]
        return {"preco": papel["SctyQtn"]["curPrc"], "variacao_dia": papel["SctyQtn"].get("prcFlcn"),
                "data": dados["Msg"]["dtTm"][:10]}
    except (TypeError, KeyError, IndexError):
        return None


def historico_yahoo(ticker):
    """Proventos por ação (todos os anos) e cotação semanal de 10 anos. Falha silenciosa -> vazio."""
    try:
        import yfinance as yf
        t = yf.Ticker(f"{ticker}.SA")
        divs = t.dividends
        hist = t.history(period="10y", interval="1wk", auto_adjust=False)
    except Exception:
        return {}, {}
    por_ano = {}
    if divs is not None and not divs.empty:
        por_ano = {str(a): round(float(v), 6) for a, v in divs.groupby(divs.index.year).sum().items()}
    cotacao = {}
    if hist is not None and not hist.empty:
        fech = hist["Close"].dropna()
        cotacao = {"datas": [d.strftime("%Y-%m-%d") for d in fech.index], "fechamento": [round(float(v), 2) for v in fech]}
    return por_ano, cotacao


def ultimo_fechamento_yahoo(ticker):
    try:
        import yfinance as yf
        hist = yf.Ticker(f"{ticker}.SA").history(period="3mo", auto_adjust=False)["Close"].dropna()
    except Exception:
        return None
    if hist.empty:
        return None
    return {"preco": round(float(hist.iloc[-1]), 2), "variacao_dia": None, "data": hist.index[-1].strftime("%Y-%m-%d"),
            "fonte": "Yahoo (último fechamento)"}


def _classe_ticker(t):
    return {"3": "ON", "4": "PN", "5": "PNA", "6": "PNB", "11": "UNIT"}.get(t[4:], t[4:])


def market_cap(acoes_on, acoes_pn, precos):
    """Ações ON e PN (B3) × preço da classe; classe sem cotação usa o preço da classe cotada."""
    preco_on = precos.get("ON")
    preco_pn = next((precos[c] for c in ("PN", "PNA", "PNB") if precos.get(c)), None)
    if preco_on is None and preco_pn is None:
        return None
    preco_on = preco_on if preco_on is not None else preco_pn
    preco_pn = preco_pn if preco_pn is not None else preco_on
    total = acoes_on * preco_on + acoes_pn * preco_pn
    return total or None


def gerar(pausa=0.2):
    DIR_PROVENTOS.mkdir(parents=True, exist_ok=True)
    universo = universo_selecionado()
    resumo, falhas = [], []
    hoje = date.today()
    for i, e in enumerate(universo.itertuples(), start=1):
        id_ = e.tickers_lista[0]
        b3 = dados_b3_empresa(id_[:4])
        precos, cotacoes = {}, {}
        for t in e.tickers_lista:
            c = cotacao_b3(t)
            time.sleep(pausa)
            if c and c["preco"]:
                cotacoes[t] = c
                precos.setdefault(_classe_ticker(t), c["preco"])
        if not b3:
            falhas.append(f"{e.DENOM_SOCIAL}: B3 não retornou dados da empresa ({id_[:4]})")
        if not cotacoes:
            # Papel pouco líquido sem negócio no último pregão: usa o último fechamento do Yahoo
            for t in sorted(e.tickers_lista, key=lambda x: x.endswith("11")):
                c = ultimo_fechamento_yahoo(t)
                if c:
                    cotacoes[t] = c
                    precos.setdefault(_classe_ticker(t), c["preco"])
            falhas.append(f"{e.DENOM_SOCIAL}: sem cotação na B3" + (" (usado último fechamento do Yahoo)" if cotacoes else " nem no Yahoo"))

        # papel de referência: o mais negociado entre os cotados não-unit; se só houver unit, a unit
        principal = next((t for t in e.tickers_lista if t in cotacoes and not t.endswith("11")), None) \
            or next((t for t in e.tickers_lista if t in cotacoes), None)
        provento_anual, cotacao_hist = historico_yahoo(principal) if principal else ({}, {})

        proventos_b3 = (b3 or {}).get("proventos", [])
        classe_ref = _classe_ticker(principal) if principal else None
        limite = (pd.Timestamp(hoje) - pd.Timedelta(days=365)).date().isoformat()
        prov_12m = sum(p["valor"] or 0 for p in proventos_b3
                       if p["classe"] == classe_ref and p["data_com"] and limite <= p["data_com"] <= hoje.isoformat())
        preco_ref = cotacoes.get(principal, {}).get("preco") if principal else None
        mcap = market_cap(b3["acoes_on"], b3["acoes_pn"], precos) if b3 else None

        (DIR_PROVENTOS / f"{id_}.json").write_text(json.dumps({
            "id": id_, "papel_referencia": principal, "proventos_b3": proventos_b3,
            "proventos_por_acao_ano": provento_anual, "cotacao_semanal": cotacao_hist,
        }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

        resumo.append({
            "id": id_, "papel_referencia": principal, "cotacoes": cotacoes,
            "acoes_on": (b3 or {}).get("acoes_on"), "acoes_pn": (b3 or {}).get("acoes_pn"),
            "segmento": (b3 or {}).get("segmento"), "market_cap": mcap,
            "proventos_12m_por_acao": round(prov_12m, 6) if prov_12m else 0.0,
            "dy_12m": (prov_12m / preco_ref) if (prov_12m and preco_ref) else None,
            "proximos_proventos": [p for p in proventos_b3 if p["data_com"] and p["data_com"] >= hoje.isoformat()],
        })
        if i % 25 == 0:
            print(f"   {i}/{len(universo)} empresas")

    (DIR_DADOS_SITE / "mercado.json").write_text(json.dumps(
        {"gerado_em": hoje.isoformat(), "empresas": resumo}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"✅ mercado: {len(resumo)} empresas; {len(falhas)} avisos")
    for f in falhas:
        print("   ⚠️", f)
    return resumo, falhas


if __name__ == "__main__":
    gerar()
