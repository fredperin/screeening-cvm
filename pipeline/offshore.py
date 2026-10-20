"""
Dados do exterior (Offshore), só de fontes oficiais e sem cadastro:

- Tesouro dos EUA: curvas de Treasuries nominal e real (TIPS), arquivo diário oficial;
- Fed de Nova York: Fed Funds efetivo (com a banda da meta) e SOFR (API oficial);
- BLS (EUA): inflação ao consumidor (CPI e núcleo), desemprego e payroll (API oficial; usa a chave
  BLS_API_KEY se existir, senão a versão sem cadastro, limitada a 25 consultas por dia);
- BCE: €STR, taxa de depósito e curva de juros AAA da Zona do Euro (API oficial);
- Eurostat: inflação (HICP, núcleo e serviços), desemprego e PIB da Zona do Euro (API oficial).

Cada fonte que falhar fica com a versão anterior (registrada em "falhas"). Saída: site/dados/offshore.json.
Uso: py -m pipeline.offshore
"""

import csv
import io
import json
import os
import time
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests

from pipeline import DIR_DADOS_SITE

CABECALHO = {"User-Agent": "Mozilla/5.0 (Bloomberg de Pobre; uso pessoal)"}
FUSO_BR = timezone(timedelta(hours=-3))
ANOS_HISTORICO = 10
DATAS_REFERENCIA = {"hoje": 0, "1 semana": 7, "1 mês": 30, "6 meses": 182, "1 ano": 365}
ARQ = DIR_DADOS_SITE / "offshore.json"


def _get(url, tentativas=3, headers=None, **kw):
    for i in range(tentativas):
        try:
            r = requests.get(url, headers=headers or CABECALHO, timeout=90, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if i == tentativas - 1:
                raise
            time.sleep(3 * (i + 1))


def _serie(s, casas=4):
    s = s.dropna().sort_index()
    return {"datas": [d.strftime("%Y-%m-%d") for d in s.index], "valores": [round(float(v), casas) for v in s.values]}


def _curvas_por_data(tabela, prazos):
    """tabela: DataFrame (índice = data) com uma coluna por prazo; devolve as curvas nas 5 datas de comparação."""
    tabela = tabela.dropna(how="all").sort_index()
    ultima = tabela.index.max()
    saida = {}
    for rotulo, dias in DATAS_REFERENCIA.items():
        candidatas = tabela.index[tabela.index <= ultima - pd.Timedelta(days=dias)]
        if not len(candidatas):
            continue
        dia = candidatas.max()
        linha = tabela.loc[dia]
        saida[rotulo] = {"data": dia.strftime("%Y-%m-%d"),
                         "pontos": [{"prazo": p, "anos": anos, "taxa": round(float(linha[p]), 4)}
                                    for p, anos in prazos.items() if p in linha and pd.notna(linha[p])]}
    return saida


# ---------------- Tesouro dos EUA ----------------
URL_UST = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{ano}/all"
           "?type={tipo}&field_tdr_date_value={ano}&page&_format=csv")
PRAZOS_UST = {"1 Mo": 1 / 12, "2 Mo": 2 / 12, "3 Mo": 0.25, "4 Mo": 4 / 12, "6 Mo": 0.5, "1 Yr": 1, "2 Yr": 2, "3 Yr": 3,
              "5 Yr": 5, "7 Yr": 7, "10 Yr": 10, "20 Yr": 20, "30 Yr": 30}
PRAZOS_TIPS = {"5 YR": 5, "7 YR": 7, "10 YR": 10, "20 YR": 20, "30 YR": 30}


def _ust(tipo):
    partes = []
    for ano in range(date.today().year - ANOS_HISTORICO, date.today().year + 1):
        texto = _get(URL_UST.format(ano=ano, tipo=tipo)).text
        if texto.strip():
            partes.append(pd.read_csv(io.StringIO(texto)))
    df = pd.concat(partes, ignore_index=True)
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
    return df.drop_duplicates("Date").set_index("Date").sort_index().apply(pd.to_numeric, errors="coerce")


def treasuries():
    nominal, real = _ust("daily_treasury_yield_curve"), _ust("daily_treasury_real_yield_curve")
    return {
        "nominal": _curvas_por_data(nominal, PRAZOS_UST),
        "real": _curvas_por_data(real, PRAZOS_TIPS),
        "historico": {"2 anos": _serie(nominal["2 Yr"]), "10 anos": _serie(nominal["10 Yr"]), "30 anos": _serie(nominal["30 Yr"]),
                      "10 anos real (TIPS)": _serie(real["10 YR"]),
                      "inclinação 10a − 2a": _serie(nominal["10 Yr"] - nominal["2 Yr"])},
    }


# ---------------- Fed de Nova York ----------------
URL_NYFED = "https://markets.newyorkfed.org/api/rates/{grupo}/{taxa}/search.json?startDate={ini}&endDate={fim}"


def fed():
    ini, fim = f"{date.today().year - ANOS_HISTORICO}-01-01", date.today().isoformat()
    effr = _get(URL_NYFED.format(grupo="unsecured", taxa="effr", ini=ini, fim=fim)).json()["refRates"]
    sofr = _get(URL_NYFED.format(grupo="secured", taxa="sofr", ini=ini, fim=fim)).json()["refRates"]
    e = pd.DataFrame(effr)
    e["effectiveDate"] = pd.to_datetime(e["effectiveDate"])
    e = e.set_index("effectiveDate").sort_index()
    s = pd.DataFrame(sofr)
    s["effectiveDate"] = pd.to_datetime(s["effectiveDate"])
    s = s.set_index("effectiveDate").sort_index()
    # banda da meta: só os dias em que mudou (gráfico em degraus)
    banda = e[["targetRateFrom", "targetRateTo"]].dropna()
    mudou = banda.ne(banda.shift()).any(axis=1)
    banda = pd.concat([banda[mudou], banda.iloc[[-1]]]).pipe(lambda b: b[~b.index.duplicated()])
    return {"effr": _serie(e["percentRate"]), "sofr": _serie(s["percentRate"]),
            "meta_min": _serie(banda["targetRateFrom"]), "meta_max": _serie(banda["targetRateTo"])}


# ---------------- BLS (EUA) ----------------
SERIES_BLS = {
    "CUUR0000SA0": "cpi", "CUUR0000SA0L1E": "cpi_nucleo", "CUSR0000SA0": "cpi_sa", "CUSR0000SA0L1E": "cpi_nucleo_sa",
    "LNS14000000": "desemprego", "CES0000000001": "payroll",
}


def bls():
    chave = os.environ.get("BLS_API_KEY")
    url = "https://api.bls.gov/publicAPI/" + ("v2" if chave else "v1") + "/timeseries/data/"
    fim = date.today().year
    series = {}
    # sem chave, a API devolve no máximo 10 anos por consulta
    for ini in ([fim - 19] if chave else [fim - 9]):
        corpo = {"seriesid": list(SERIES_BLS), "startyear": str(ini), "endyear": str(fim)}
        if chave:
            corpo["registrationkey"] = chave
        r = requests.post(url, json=corpo, headers=CABECALHO, timeout=90).json()
        if r.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError(f"BLS: {r.get('status')} {r.get('message')}")
        for s in r["Results"]["series"]:
            pontos = {pd.Timestamp(int(x["year"]), int(x["period"][1:]), 1): float(x["value"])
                      for x in s["data"] if x["period"].startswith("M") and x["period"] != "M13" and x["value"] not in ("-", "")}
            series[SERIES_BLS[s["seriesID"]]] = pd.Series(pontos).sort_index()
    cpi, nuc = series["cpi"], series["cpi_nucleo"]
    return {
        "cpi_12m": _serie((cpi / cpi.shift(12) - 1) * 100), "cpi_nucleo_12m": _serie((nuc / nuc.shift(12) - 1) * 100),
        "cpi_mensal": _serie((series["cpi_sa"] / series["cpi_sa"].shift(1) - 1) * 100),
        "cpi_nucleo_mensal": _serie((series["cpi_nucleo_sa"] / series["cpi_nucleo_sa"].shift(1) - 1) * 100),
        "desemprego": _serie(series["desemprego"]),
        "payroll_var": _serie(series["payroll"].diff(), 1),  # milhares de vagas criadas no mês
        "fonte_chave": bool(chave),
    }


# ---------------- BCE e Eurostat ----------------
URL_BCE = "https://data-api.ecb.europa.eu/service/data/{chave}?startPeriod={ini}&format=csvdata"


def _bce(chave, ini=None):
    ini = ini or f"{date.today().year - ANOS_HISTORICO}-01-01"
    texto = _get(URL_BCE.format(chave=chave, ini=ini)).text
    linhas = list(csv.DictReader(io.StringIO(texto)))
    if not linhas:
        raise ValueError(f"BCE {chave}: vazio")
    return linhas


def _bce_serie(chave, mensal=False, ini=None):
    linhas = _bce(chave, ini)
    idx = [pd.Timestamp(l["TIME_PERIOD"] + ("-01" if mensal else "")) for l in linhas]
    return pd.Series([float(l["OBS_VALUE"]) for l in linhas], index=idx).sort_index()


PRAZOS_BCE = {"SR_3M": 0.25, "SR_6M": 0.5, "SR_1Y": 1, "SR_2Y": 2, "SR_3Y": 3, "SR_5Y": 5, "SR_7Y": 7, "SR_10Y": 10,
              "SR_15Y": 15, "SR_20Y": 20, "SR_30Y": 30}


def bce():
    deposito = _bce_serie("FM/B.U2.EUR.4F.KR.DFR.LEV", ini="1999-01-01")
    mudou = deposito.ne(deposito.shift())
    deposito = pd.concat([deposito[mudou], deposito.iloc[[-1]]]).pipe(lambda s: s[~s.index.duplicated()])
    linhas = _bce("YC/B.U2.EUR.4F.G_N_A.SV_C_YM." + "+".join(PRAZOS_BCE), ini=(date.today() - timedelta(days=400)).isoformat())
    tabela = pd.DataFrame([{"data": pd.Timestamp(l["TIME_PERIOD"]), "prazo": l["KEY"].split(".")[-1], "taxa": float(l["OBS_VALUE"])}
                           for l in linhas]).pivot_table(index="data", columns="prazo", values="taxa")
    curva10 = _bce_serie("YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y")
    return {
        "estr": _serie(_bce_serie("EST/B.EU000A2X2A25.WT")), "deposito": _serie(deposito),
        "curva": _curvas_por_data(tabela, PRAZOS_BCE), "aaa_10a": _serie(curva10),
    }


URL_EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{tabela}?{filtro}&sinceTimePeriod={ini}"


def _eurostat(tabela, filtro, ini):
    d = _get(URL_EUROSTAT.format(tabela=tabela, filtro=filtro, ini=ini)).json()
    tempo = d["dimension"]["time"]["category"]["index"]  # período -> posição
    valores = {int(k): v for k, v in d["value"].items()}
    pontos = {}
    for periodo, pos in tempo.items():
        if pos in valores:
            if "Q" in periodo:
                ano, tri = periodo.split("-Q")
                quando = pd.Timestamp(int(ano), 3 * int(tri) - 2, 1)
            else:
                quando = pd.Timestamp(periodo + "-01")
            pontos[quando] = valores[pos]
    return pd.Series(pontos).sort_index()


# Zona do Euro com 21 países desde a entrada da Bulgária (2026); "EA" é a composição de cada época
ZONA_EURO = "EA21"


def eurostat():
    # HICP pela classificação ECOICOP ver.2 (a série antiga, prc_hicp_manr, parou em dez/2025)
    return {
        "hicp_12m": _serie(_eurostat("prc_hicp_minr", "geo=EA&unit=RCH_A&coicop18=TOTAL", "2000-01")),
        "hicp_nucleo_12m": _serie(_eurostat("prc_hicp_minr", "geo=EA&unit=RCH_A&coicop18=TOT_X_NRG_FOOD", "2000-01")),
        "hicp_servicos_12m": _serie(_eurostat("prc_hicp_minr", "geo=EA&unit=RCH_A&coicop18=SERV", "2000-01")),
        "desemprego": _serie(_eurostat("une_rt_m", f"geo={ZONA_EURO}&s_adj=SA&age=TOTAL&sex=T&unit=PC_ACT", "2000-01")),
        "pib_tri": _serie(_eurostat("namq_10_gdp", f"geo={ZONA_EURO}&unit=CLV_PCH_PRE&s_adj=SCA&na_item=B1GQ", "2000-Q1")),
        "pib_12m": _serie(_eurostat("namq_10_gdp", f"geo={ZONA_EURO}&unit=CLV_PCH_SM&s_adj=SCA&na_item=B1GQ", "2000-Q1")),
    }


# ---------------- Notícias e agenda do exterior ----------------
FEEDS = {"Federal Reserve": "https://www.federalreserve.gov/feeds/press_all.xml", "BCE": "https://www.ecb.europa.eu/rss/press.html"}
# notícias de mercado do exterior: RSS públicos, só manchete e link
FEEDS_MERCADO = {
    "WSJ": "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",
    "Financial Times": "https://www.ft.com/markets?format=rss",
    "CNBC": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "The Guardian": "https://www.theguardian.com/business/rss",
    "BBC": "https://feeds.bbci.co.uk/news/business/rss.xml",
}
NAVEGADOR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"}
MESES_EN = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September",
                                         "October", "November", "December"], 1)}
MESES_EN.update({m[:3]: i for m, i in list(MESES_EN.items())})


def noticias():
    from pipeline.noticias import ler_feed
    itens, falhas = [], []
    for tipo, feeds in (("oficial", FEEDS), ("mercado", FEEDS_MERCADO)):
        for fonte, url in feeds.items():
            try:
                itens += ler_feed(fonte, url, tipo)
            except Exception as e:
                falhas.append(f"{fonte}: {e!r}"[:200])
    limites = {"oficial": (date.today() - timedelta(days=60)).isoformat(), "mercado": (date.today() - timedelta(days=7)).isoformat()}
    itens = sorted({i["link"]: i for i in itens if i["data"][:10] >= limites[i["tipo"]]}.values(), key=lambda i: i["data"], reverse=True)[:500]
    return itens, falhas


def fomc():
    """Reuniões do FOMC na página oficial do Fed; a decisão sai no segundo dia, às 15h de Washington."""
    import html as _html
    import re
    texto = _get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm", headers=NAVEGADOR).text
    texto = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " | ", texto)))
    eventos = []
    blocos = re.split(r"(\d{4}) FOMC Meetings", texto)
    for ano, bloco in zip(blocos[1::2], blocos[2::2]):
        for mes, d1, d2, sep in re.findall(r"\| ([A-Z][a-z]{2,8}(?:/[A-Z][a-z]{2,8})?) [| ]*?(\d{1,2})-(\d{1,2})(\*?) \|", bloco):
            # "Apr/May 30-1": o segundo dia cai no segundo mês
            meses = mes.split("/")
            if any(x not in MESES_EN for x in meses):
                continue
            quando = date(int(ano), MESES_EN[meses[-1]], int(d2))
            eventos.append({"data": quando.isoformat(), "evento": "FOMC — decisão de juros", "categoria": "fed", "fonte": "Federal Reserve",
                            "detalhe": "Reunião de 2 dias; comunicado às 15h de Washington" + (" e projeções econômicas" if sep else "")})
    if len(eventos) < 4:
        raise ValueError("calendário do FOMC não reconhecido")
    return eventos


def reunioes_bce():
    import html as _html
    import re
    texto = _get("https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html", headers=NAVEGADOR).text
    pares = re.findall(r"<dt>\s*(\d{2}/\d{2}/\d{4})\s*</dt>\s*<dd>(.*?)</dd>", texto, re.S)
    eventos = [{"data": datetime.strptime(d, "%d/%m/%Y").date().isoformat(), "evento": "BCE — decisão de juros", "categoria": "bce",
                "fonte": "BCE", "detalhe": "Segundo dia da reunião de política monetária, seguido de entrevista coletiva"}
               for d, texto_dd in pares if "monetary policy meeting" in texto_dd and "Day 2" in texto_dd and "non-monetary" not in texto_dd]
    if not eventos:
        raise ValueError("calendário do BCE não reconhecido")
    return eventos


def gerar_noticias_agenda():
    hoje = date.today().isoformat()
    itens, falhas = noticias()
    eventos = []
    for nome, funcao in (("Federal Reserve (FOMC)", fomc), ("BCE (reuniões)", reunioes_bce)):
        try:
            eventos += funcao()
        except Exception as e:
            falhas.append(f"{nome}: {e!r}"[:200])
    eventos = sorted({(e["data"], e["evento"]): e for e in eventos if e["data"] >= hoje}.values(), key=lambda e: e["data"])
    agora = datetime.now(FUSO_BR).isoformat(timespec="minutes")
    (DIR_DADOS_SITE / "noticias_offshore.json").write_text(json.dumps({"gerado_em": agora, "itens": itens, "falhas": [f for f in falhas if "FOMC" not in f and "reuniões" not in f]},
                                                                     ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (DIR_DADOS_SITE / "agenda_offshore.json").write_text(json.dumps({"gerado_em": date.today().isoformat(), "eventos": eventos,
                                                                     "falhas": [f for f in falhas if "FOMC" in f or "reuniões" in f]},
                                                                    ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"✅ offshore notícias: {len(itens)}; agenda: {len(eventos)} eventos; falhas: {falhas or 'nenhuma'}")
    return falhas


FONTES = {"treasuries": ("Tesouro dos EUA", treasuries), "fed": ("Fed de Nova York", fed), "bls": ("BLS (EUA)", bls),
          "bce": ("BCE", bce), "eurostat": ("Eurostat", eurostat)}


def gerar():
    anterior = json.loads(ARQ.read_text(encoding="utf-8")) if ARQ.exists() else {}
    saida, falhas = {}, []
    for chave, (nome, funcao) in FONTES.items():
        try:
            saida[chave] = funcao()
        except Exception as e:
            falhas.append(f"{nome}: {e!r}"[:300])
            if chave in anterior:
                saida[chave] = anterior[chave]  # fica a versão anterior
    try:
        falhas += gerar_noticias_agenda()
    except Exception as e:
        falhas.append(f"notícias e agenda: {e!r}"[:300])
    ARQ.write_text(json.dumps({"gerado_em": datetime.now(FUSO_BR).isoformat(timespec="minutes"), **saida, "falhas": falhas},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"✅ offshore: {', '.join(saida)}; falhas: {falhas or 'nenhuma'} ({ARQ.stat().st_size // 1024} KB)")
    if all(nome not in saida for nome in FONTES):
        raise RuntimeError("nenhuma fonte do exterior respondeu")
    return ARQ


if __name__ == "__main__":
    gerar()
    d = json.loads(ARQ.read_text(encoding="utf-8"))
    ult = lambda s: (s["datas"][-1], s["valores"][-1]) if s and s["datas"] else None
    if "treasuries" in d:
        print("UST hoje", d["treasuries"]["nominal"]["hoje"]["data"], [(p["prazo"], p["taxa"]) for p in d["treasuries"]["nominal"]["hoje"]["pontos"]][:6])
        print("TIPS hoje", d["treasuries"]["real"]["hoje"])
    if "fed" in d:
        print("EFFR", ult(d["fed"]["effr"]), "SOFR", ult(d["fed"]["sofr"]), "meta", ult(d["fed"]["meta_min"]), ult(d["fed"]["meta_max"]))
    if "bls" in d:
        print("CPI 12m", ult(d["bls"]["cpi_12m"]), "núcleo", ult(d["bls"]["cpi_nucleo_12m"]), "desemprego", ult(d["bls"]["desemprego"]),
              "payroll", ult(d["bls"]["payroll_var"]), "pontos", len(d["bls"]["cpi_12m"]["datas"]))
    if "bce" in d:
        print("€STR", ult(d["bce"]["estr"]), "depósito", ult(d["bce"]["deposito"]), "AAA 10a", ult(d["bce"]["aaa_10a"]))
        print("curva BCE hoje", d["bce"]["curva"].get("hoje"))
    if "eurostat" in d:
        e = d["eurostat"]
        print("HICP", ult(e["hicp_12m"]), "núcleo", ult(e["hicp_nucleo_12m"]), "serviços", ult(e["hicp_servicos_12m"]), len(e["hicp_12m"]["datas"]))
        print("desemprego", ult(e["desemprego"]), len(e["desemprego"]["datas"]), "PIB tri", ult(e["pib_tri"]), "PIB 12m", ult(e["pib_12m"]), len(e["pib_tri"]["datas"]))
