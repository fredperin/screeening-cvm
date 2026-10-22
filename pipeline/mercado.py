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

from config.config import RAW_DIR
from pipeline import DIR_DADOS_SITE
from src.screening import universo_perfis as universo_selecionado  # empresas + bancos listados

URL_EMPRESA = "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/GetListedSupplementCompany/{}"
URL_COTACAO = "https://cotacao.b3.com.br/mds/api/v1/instrumentQuotation/{}"
URL_HISTORICO = "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/GetListedCashDividends/{}"
ANOS_PROVENTOS_LISTA = 3
CABECALHO = {"User-Agent": "Mozilla/5.0"}
DIR_PROVENTOS = DIR_DADOS_SITE / "proventos"
DIR_YAHOO = RAW_DIR / "yahoo"  # cópia local do histórico do Yahoo (guardada no cache do GitHub Actions)
DIR_YAHOO.mkdir(parents=True, exist_ok=True)
COMPLETO_YAHOO_DIAS = 7
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
        "nome_pregao": (d.get("tradingName") or "").strip(),
        "proventos": sorted(proventos, key=lambda p: p["data_com"] or "", reverse=True),
    }


def historico_proventos_b3(nome_pregao):
    """O nome aceito pela consulta de histórico às vezes difere do nome de pregão (KLABIN S/A x KLABIN S.A.)."""
    base = (nome_pregao or "").strip()
    variantes = [base, base.replace("S/A", "S.A."), base.replace("S.A.", "S/A"), f"{base} S.A.",
                 base.replace(" S/A", "").replace(" S.A.", "")]
    for nome in dict.fromkeys(v for v in variantes if v):
        resultado = _historico_proventos_b3(nome)
        if resultado:
            return resultado
    return []


def _historico_proventos_b3(nome_pregao):
    """
    Histórico completo de proventos em dinheiro na B3 (todas as páginas): tipo, classe,
    data de aprovação, data-com, valor por ação e preço de fechamento na data-com.
    Não traz a data de pagamento (essa só vem, para ~12 meses, em GetListedSupplementCompany).
    """
    saida, pagina = [], 1
    while nome_pregao:
        params = base64.b64encode(json.dumps({"language": "pt-br", "pageNumber": pagina, "pageSize": 120,
                                              "tradingName": nome_pregao}).encode()).decode()
        dados = _get_json(URL_HISTORICO.format(params))
        if not dados or not dados.get("results"):
            break
        for p in dados["results"]:
            acao = (p.get("corporateAction") or "").upper()
            saida.append({
                "tipo": "JCP" if "JRS" in acao else acao.title(), "classe": (p.get("typeStock") or "").upper(),
                "valor": _num_br(p.get("valueCash")), "data_com": _data_br(p.get("lastDatePriorEx")),
                "aprovado": _data_br(p.get("dateApproval")), "preco_data_com": _num_br(p.get("closingPricePriorExDate")),
                "fator_cotacao": _num_br(p.get("quotedPerShares")) or 1,
            })
        if pagina >= (dados.get("page") or {}).get("totalPages", 1):
            break
        pagina += 1
    return [p for p in saida if p["data_com"] and p["valor"] is not None]


def cotacao_b3(ticker):
    dados = _get_json(URL_COTACAO.format(ticker))
    try:
        papel = dados["Trad"][0]["scty"]
        return {"preco": papel["SctyQtn"]["curPrc"], "variacao_dia": papel["SctyQtn"].get("prcFlcn"),
                "data": dados["Msg"]["dtTm"][:10]}
    except (TypeError, KeyError, IndexError):
        return None


def _semanal(hist):
    if hist is None or hist.empty:
        return {}
    fech = hist["Close"].dropna()
    return {"datas": [d.strftime("%Y-%m-%d") for d in fech.index], "fechamento": [round(float(v), 2) for v in fech]}


def _historico_yahoo_completo(t):
    divs = t.dividends
    hist = t.history(period="10y", interval="1wk", auto_adjust=False)
    proventos = []  # lista [data, valor]: pode haver dois proventos na mesma data
    if divs is not None and not divs.empty:
        proventos = [[d.strftime("%Y-%m-%d"), float(v)] for d, v in divs.items()]
    return proventos, _semanal(hist)


def historico_yahoo(ticker):
    """Proventos por ação (todos os anos) e cotação semanal de 10 anos. Falha silenciosa -> vazio.

    Com cópia local (data/raw/yahoo), nos dias comuns baixa só os últimos 3 meses e junta ao histórico.
    Só aceita a junção se o resultado for o mesmo do download completo: as semanas em comum precisam
    bater (desdobramento ou ajuste do Yahoo muda o passado) e não pode haver provento novo na janela;
    senão, e a cada COMPLETO_YAHOO_DIAS dias, baixa tudo de novo."""
    arq = DIR_YAHOO / f"{ticker}.json"
    hoje = date.today()
    try:
        guardado = json.loads(arq.read_text(encoding="utf-8"))
        idade = (hoje - date.fromisoformat(guardado["completo_em"])).days
    except (OSError, ValueError, KeyError):
        guardado, idade = None, None
    try:
        import yfinance as yf
        t = yf.Ticker(f"{ticker}.SA")
        proventos, cotacao = None, None
        dez_anos = pd.Timestamp(hoje) - pd.DateOffset(years=10)
        corte = (dez_anos - pd.Timedelta(days=dez_anos.weekday())).strftime("%Y-%m-%d")
        datas_guardadas = (guardado or {}).get("cotacao", {}).get("datas") or []
        # data mais antiga já vista do papel: uma resposta que começa bem depois dela veio cortada (Yahoo, 22/10/2026:
        # Localiza só a partir de dez/2025). Sem esse registro e com histórico curto, recarrega tudo uma vez para conferir.
        inicio_conhecido = (guardado or {}).get("inicio_conhecido") or (datas_guardadas[0] if datas_guardadas else None)
        conferir_corte = bool(guardado) and "inicio_conhecido" not in guardado and bool(datas_guardadas) and \
            datas_guardadas[0] > (pd.Timestamp(corte) + pd.Timedelta(days=30)).strftime("%Y-%m-%d")
        if guardado and idade < COMPLETO_YAHOO_DIAS and datas_guardadas and not conferir_corte:
            hist = t.history(period="3mo", interval="1wk", auto_adjust=False)
            recente = _semanal(hist)
            antigo = dict(zip(guardado["cotacao"]["datas"], guardado["cotacao"]["fechamento"]))
            novo = dict(zip(recente.get("datas", []), recente.get("fechamento", [])))
            comuns = [d for d in novo if d in antigo][:-1]  # a última semana ainda está em formação
            inicio = recente["datas"][0] if recente else None
            prov_janela = round(float(hist["Dividends"].sum()), 8) if "Dividends" in hist else None
            prov_guardado = round(sum(v for d, v in guardado["proventos"] if inicio and d >= inicio), 8)
            if comuns and all(antigo[d] == novo[d] for d in comuns) and prov_janela is not None \
                    and abs(prov_janela - prov_guardado) < 1e-6:
                # mesma janela do completo: semana (começa na segunda) que contém o dia de 10 anos atrás
                junto = {d: v for d, v in antigo.items() if d < inicio and d >= corte} | novo
                datas = sorted(junto)
                proventos, cotacao = guardado["proventos"], {"datas": datas, "fechamento": [junto[d] for d in datas]}
                arq.write_text(json.dumps({**guardado, "cotacao": cotacao, "inicio_conhecido": inicio_conhecido}), encoding="utf-8")
        if cotacao is None:
            proventos, cotacao = _historico_yahoo_completo(t)
            datas_novas = (cotacao or {}).get("datas") or []
            limite = (pd.Timestamp(max(inicio_conhecido or corte, corte)) + pd.Timedelta(days=30)).strftime("%Y-%m-%d")
            if datas_guardadas and datas_novas and datas_novas[0] > limite:
                # resposta cortada: o histórico guardado não é apagado. Junta as semanas novas se as semanas em comum batem;
                # se não batem (desdobramento ou ajuste no meio), fica o guardado e o completo é tentado de novo amanhã
                antigo = dict(zip(datas_guardadas, guardado["cotacao"]["fechamento"]))
                novo = dict(zip(datas_novas, cotacao["fechamento"]))
                comuns = [d for d in novo if d in antigo][:-1]
                if comuns and all(abs(antigo[d] - novo[d]) <= 1e-6 * max(abs(antigo[d]), 1) for d in comuns):
                    junto = {d: v for d, v in antigo.items() if d >= corte} | novo
                    datas = sorted(junto)
                    cotacao = {"datas": datas, "fechamento": [junto[d] for d in datas]}
                    proventos = [list(x) for x in sorted({tuple(x) for x in guardado["proventos"] if x[0] < datas_novas[0]}
                                                         | {tuple(x) for x in proventos or []})]
                    arq.write_text(json.dumps({"completo_em": hoje.isoformat(), "proventos": proventos, "cotacao": cotacao,
                                               "inicio_conhecido": inicio_conhecido}), encoding="utf-8")
                else:
                    proventos, cotacao = guardado["proventos"], guardado["cotacao"]
            else:
                inicio = min([x for x in (inicio_conhecido, datas_novas[0] if datas_novas else None) if x] or [None])
                arq.write_text(json.dumps({"completo_em": hoje.isoformat(), "proventos": proventos, "cotacao": cotacao,
                                           "inicio_conhecido": inicio}), encoding="utf-8")
    except Exception:
        return {}, {}
    por_ano = {}
    if proventos:  # mesma soma por ano (pandas) do download direto
        s = pd.Series([v for _, v in proventos], index=[int(d[:4]) for d, _ in proventos])
        por_ano = {str(a): round(float(v), 6) for a, v in s.groupby(level=0).sum().items()}
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


def gerar(pausa=0.2, filtro=None):
    DIR_PROVENTOS.mkdir(parents=True, exist_ok=True)
    universo = universo_selecionado()
    if filtro:
        universo = universo[universo["tickers_lista"].apply(lambda ts: ts[0] in filtro)]
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

        recentes = (b3 or {}).get("proventos", [])
        historico = historico_proventos_b3((b3 or {}).get("nome_pregao"))
        # data de pagamento: só a API de ~12 meses tem; casa por classe + data-com + valor
        pagamentos = {}
        for p in recentes:
            pagamentos.setdefault((p["classe"], p["data_com"], round(p["valor"] or 0, 8)), []).append(p)
        classe_ref = _classe_ticker(principal) if principal else None
        if classe_ref == "UNIT":
            classe_ref = "UNT"
        limite_lista = date(hoje.year - ANOS_PROVENTOS_LISTA, hoje.month, min(hoje.day, 28)).isoformat()
        proventos_b3 = []
        for p in sorted(historico, key=lambda x: x["data_com"], reverse=True):
            if p["data_com"] < limite_lista:
                continue
            casados = pagamentos.get((p["classe"], p["data_com"], round(p["valor"], 8))) or [None]
            for c in casados:  # um anúncio pago em parcelas vira uma linha por parcela
                proventos_b3.append({**p, "pagamento": c["pagamento"] if c else None,
                                     "referente": c["referente"] if c else None})
        if not historico:  # B3 sem histórico: fica com os ~12 meses da outra API
            proventos_b3 = recentes

        def classe_igual(c):
            return c == classe_ref
        limite = (pd.Timestamp(hoje) - pd.Timedelta(days=365)).date().isoformat()
        base_12m = historico or recentes
        prov_12m = sum(p["valor"] or 0 for p in base_12m
                       if classe_igual(p["classe"]) and limite <= p["data_com"] <= hoje.isoformat())
        # Proventos por ação e DY por ano, oficiais da B3: soma por ano da data-com; DY do ano =
        # soma de (valor ÷ preço de fechamento na data-com), ou seja, o yield de cada provento no dia
        por_ano_b3, dy_ano_b3 = {}, {}
        for p in historico:
            if not classe_igual(p["classe"]):
                continue
            ano = p["data_com"][:4]
            por_ano_b3[ano] = round(por_ano_b3.get(ano, 0) + p["valor"], 6)
            if p["preco_data_com"]:
                dy_ano_b3[ano] = round(dy_ano_b3.get(ano, 0) + p["valor"] * p["fator_cotacao"] / p["preco_data_com"], 6)
        preco_ref = cotacoes.get(principal, {}).get("preco") if principal else None
        mcap = market_cap(b3["acoes_on"], b3["acoes_pn"], precos) if b3 else None

        (DIR_PROVENTOS / f"{id_}.json").write_text(json.dumps({
            "id": id_, "papel_referencia": principal, "classe_referencia": classe_ref,
            "proventos_b3": proventos_b3,
            "proventos_por_acao_ano": por_ano_b3 or provento_anual,
            "dy_ano": dy_ano_b3,
            "fonte_por_acao": "B3" if por_ano_b3 else ("Yahoo" if provento_anual else None),
            "cotacao_semanal": cotacao_hist,
        }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

        resumo.append({
            "id": id_, "papel_referencia": principal, "cotacoes": cotacoes, "nome_pregao": (b3 or {}).get("nome_pregao"),
            "acoes_on": (b3 or {}).get("acoes_on"), "acoes_pn": (b3 or {}).get("acoes_pn"),
            "segmento": (b3 or {}).get("segmento"), "market_cap": mcap,
            "proventos_12m_por_acao": round(prov_12m, 6) if prov_12m else 0.0,
            "dy_12m": (prov_12m / preco_ref) if (prov_12m and preco_ref) else None,
            # data-com ou pagamento ainda por vir (a B3 anuncia com data-com passada e pagamento em parcelas futuras)
            "proximos_proventos": [p for p in proventos_b3 if (p["data_com"] or "") >= hoje.isoformat()
                                   or (p.get("pagamento") or "") >= hoje.isoformat()],
        })
        if i % 25 == 0:
            print(f"   {i}/{len(universo)} empresas")

    arq = DIR_DADOS_SITE / "mercado.json"
    if filtro and arq.exists():  # atualização parcial: troca só as empresas pedidas
        novos = {r["id"]: r for r in resumo}
        antigos = json.loads(arq.read_text(encoding="utf-8"))["empresas"]
        resumo = [novos.pop(r["id"], r) for r in antigos] + list(novos.values())
    arq.write_text(json.dumps({"gerado_em": hoje.isoformat(), "empresas": resumo},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"✅ mercado: {len(resumo)} empresas; {len(falhas)} avisos")
    for f in falhas:
        print("   ⚠️", f)
    return resumo, falhas


if __name__ == "__main__":
    import sys
    gerar(filtro=set(sys.argv[1:]) or None)
