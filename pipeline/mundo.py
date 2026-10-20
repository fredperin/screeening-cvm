"""
Mundo — Mercados, commodities, China e Global (passos 3 a 6), só de fontes oficiais:

- Mercados (FRED, chave FRED_API_KEY): S&P 500, Nasdaq, VIX, petróleo Brent e WTI, dólar global
  (índice amplo do Fed), spreads de crédito high yield e grau de investimento (ICE BofA) e bitcoin.
  O FRED só publica os últimos 10 anos do S&P 500 (licença da S&P).
- Commodities (Banco Mundial, "Pink Sheet", mensal): petróleo, gás, carvão, minério de ferro, metais,
  ouro, prata, grãos, café, açúcar, algodão, boi etc. O endereço do arquivo muda todo mês: é lido na
  página oficial do Banco Mundial.
- China (OCDE, Key Short-Term Economic Indicators): PIB, inflação, comércio exterior, indicador
  antecedente, confiança, juros e câmbio. A OCDE recebe os dados do NBS e os mantém em séries
  contínuas. Produção industrial, varejo e desemprego vêm do espelho do NBS no DBnomics, que guarda só
  13 meses e parou de atualizar em fev/2026: entram marcados como "descontinuados" (o site mostra o aviso).
- Global (FMI, World Economic Outlook, DataMapper API): PIB, inflação, desemprego, dívida, resultado
  fiscal e conta corrente por país, com projeções (revistas em abril e outubro).

Cada parte que falhar fica com a versão anterior. Saída: site/dados/mundo.json. Uso: py -m pipeline.mundo
"""

import csv
import io
import json
import os
import re
from datetime import date, datetime

import pandas as pd
import requests

from pipeline import DIR_DADOS_SITE, DIR_INTERMEDIARIO, sem_segredos
from pipeline.offshore import FUSO_BR, NAVEGADOR, _fred, _get, _serie

ARQ = DIR_DADOS_SITE / "mundo.json"

# ---------------- Mercados (FRED) ----------------
SERIES_MERCADO = {
    "sp500": ("SP500", "S&P 500"), "nasdaq": ("NASDAQCOM", "Nasdaq Composite"), "vix": ("VIXCLS", "VIX (volatilidade do S&P 500)"),
    "brent": ("DCOILBRENTEU", "Petróleo Brent (US$/barril)"), "wti": ("DCOILWTICO", "Petróleo WTI (US$/barril)"),
    "dolar": ("DTWEXBGS", "Dólar global — índice amplo do Fed"), "hy": ("BAMLH0A0HYM2", "Spread high yield (ICE BofA, p.p.)"),
    "ig": ("BAMLC0A0CM", "Spread grau de investimento (ICE BofA, p.p.)"), "bitcoin": ("CBBTCUSD", "Bitcoin (Coinbase, US$)"),
}


def mercados():
    chave = os.environ.get("FRED_API_KEY")
    if not chave:
        raise RuntimeError("FRED_API_KEY não configurada")
    ini = f"{date.today().year - 10}-01-01"
    saida, falhas = {}, []
    for k, (cod, nome) in SERIES_MERCADO.items():
        try:
            saida[k] = {"nome": nome, **_serie(_fred(cod, chave, ini=ini), 2)}
        except Exception as e:  # uma série fora não derruba as outras
            falhas.append(sem_segredos(str(e))[:150])
    if not saida:
        raise RuntimeError("FRED (mercados): " + "; ".join(falhas[:3]))
    saida["falhas"] = falhas
    return saida


# ---------------- Commodities (Banco Mundial, Pink Sheet) ----------------
PAGINA_WB = "https://www.worldbank.org/en/research/commodity-markets"
ARQ_PINK = DIR_INTERMEDIARIO / "pink_sheet_mensal.xlsx"
# chave: (coluna na planilha "Monthly Prices", nome, unidade, grupo)
COMMODITIES = {
    "brent": ("Crude oil, Brent", "Petróleo Brent", "US$/barril", "energia"),
    "wti": ("Crude oil, WTI", "Petróleo WTI", "US$/barril", "energia"),
    "gas_eua": ("Natural gas, US", "Gás natural — EUA (Henry Hub)", "US$/MMBtu", "energia"),
    "gas_europa": ("Natural gas, Europe", "Gás natural — Europa (TTF)", "US$/MMBtu", "energia"),
    "carvao": ("Coal, Australian", "Carvão — Austrália", "US$/t", "energia"),
    "minerio": ("Iron ore, cfr spot", "Minério de ferro (China, CFR)", "US$/t seca", "metais"),
    "cobre": ("Copper", "Cobre", "US$/t", "metais"),
    "aluminio": ("Aluminum", "Alumínio", "US$/t", "metais"),
    "niquel": ("Nickel", "Níquel", "US$/t", "metais"),
    "zinco": ("Zinc", "Zinco", "US$/t", "metais"),
    "ouro": ("Gold", "Ouro", "US$/onça troy", "metais"),
    "prata": ("Silver", "Prata", "US$/onça troy", "metais"),
    "soja": ("Soybeans", "Soja", "US$/t", "agricolas"),
    "milho": ("Maize", "Milho", "US$/t", "agricolas"),
    "trigo": ("Wheat, US HRW", "Trigo (EUA, HRW)", "US$/t", "agricolas"),
    "cafe_arabica": ("Coffee, Arabica", "Café arábica", "US$/kg", "agricolas"),
    "cafe_robusta": ("Coffee, Robusta", "Café robusta", "US$/kg", "agricolas"),
    "acucar": ("Sugar, world", "Açúcar (mercado mundial)", "US$/kg", "agricolas"),
    "algodao": ("Cotton, A Index", "Algodão", "US$/kg", "agricolas"),
    "boi": ("Beef **", "Carne bovina", "US$/kg", "agricolas"),
    "frango": ("Chicken **", "Frango", "US$/kg", "agricolas"),
    "cacau": ("Cocoa", "Cacau", "US$/kg", "agricolas"),
    "laranja": ("Orange", "Laranja", "US$/kg", "agricolas"),
    "fertilizante_ureia": ("Urea ", "Ureia (fertilizante)", "US$/t", "agricolas"),
}


def _baixar_pink():
    html = _get(PAGINA_WB, headers=NAVEGADOR).text
    m = re.search(r'https://thedocs\.worldbank\.org/[^"\']*CMO-Historical-Data-Monthly\.xlsx', html)
    if not m:
        raise RuntimeError("Banco Mundial: link da planilha mensal não encontrado na página")
    ARQ_PINK.write_bytes(_get(m.group(0), headers=NAVEGADOR).content)


def commodities():
    try:
        _baixar_pink()
    except Exception:
        if not ARQ_PINK.exists():
            raise
    tab = pd.read_excel(ARQ_PINK, sheet_name="Monthly Prices", header=4)
    tab = tab.rename(columns={tab.columns[0]: "periodo"}).iloc[2:]  # linha 5 = unidades, linha 6 = início
    tab = tab[tab["periodo"].astype(str).str.match(r"^\d{4}M\d{2}$")]
    datas = pd.to_datetime(tab["periodo"].str.replace("M", "-") + "-01")
    saida = {}
    for k, (col, nome, un, grupo) in COMMODITIES.items():
        if col not in tab.columns:
            continue
        s = pd.Series(pd.to_numeric(tab[col], errors="coerce").values, index=datas).dropna()
        s = s[s.index >= "2000-01-01"]
        if not s.empty:
            saida[k] = {"nome": nome, "unidade": un, "grupo": grupo, **_serie(s, 2)}
    if len(saida) < 10:
        raise RuntimeError(f"Banco Mundial: só {len(saida)} commodities lidas (layout mudou?)")
    return saida


# ---------------- China (OCDE) ----------------
URL_OCDE_KEI = ("https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_KEI@DF_KEI,4.0/CHN.......?"
                "startPeriod=2000-01&dimensionAtObservation=AllDimensions&format=csvfile")
# chave: (frequência, medida, transformação, ajuste) -> nome
SERIES_CHINA = {
    "pib_12m": ("Q", "B1GQ_Q", "GY", "Y", "PIB — contra o mesmo trimestre do ano anterior"),
    "pib_tri": ("Q", "B1GQ_Q", "G1", "Y", "PIB — tri/tri dessazonalizado"),
    "cpi_12m": ("M", "CP", "GY", "_Z", "Inflação ao consumidor (CPI) — 12 meses"),
    "cpi_mensal": ("M", "CP", "G1", "_Z", "Inflação ao consumidor (CPI) — no mês"),
    "exportacoes_12m": ("M", "EX", "GY", "Y", "Exportações de mercadorias — 12 meses"),
    "importacoes_12m": ("M", "IM", "GY", "Y", "Importações de mercadorias — 12 meses"),
    "antecedente": ("M", "LI", "_Z", "AA", "Indicador antecedente composto (OCDE, 100 = tendência)"),
    "confianca_empresas": ("M", "BCICP", "_Z", "Y", "Confiança das empresas"),
    "confianca_consumidor": ("M", "CCICP", "_Z", "Y", "Confiança do consumidor"),
    "juros_curto": ("M", "IR3TIB", "_Z", "_Z", "Juros de curto prazo (interbancário 3 meses)"),
    "juros_longo": ("M", "IRLT", "_Z", "_Z", "Juros de longo prazo (título do governo de 10 anos)"),
    "cambio": ("M", "CC", "_Z", "_Z", "Câmbio — yuans por dólar"),
}


SERIES_NBS_DBNOMICS = {
    "producao_12m": ("M_A0201/A020101", "Valor adicionado da indústria — 12 meses"),
    "varejo_12m": ("M_A0701/A070103", "Vendas no varejo — 12 meses"),
    "desemprego": ("M_A0E01/A0E0101", "Desemprego urbano (pesquisa)"),
    "desemprego_jovens": ("M_A0E01/A0E0105", "Desemprego urbano — 16 a 24 anos"),
}


def china():
    texto = _get(URL_OCDE_KEI, headers=NAVEGADOR).text
    linhas = list(csv.DictReader(io.StringIO(texto)))
    if not linhas:
        raise RuntimeError("OCDE (China): resposta vazia")
    saida = {}
    for k, (freq, medida, transf, ajuste, nome) in SERIES_CHINA.items():
        pontos = {}
        for x in linhas:
            if (x.get("FREQ"), x.get("MEASURE"), x.get("TRANSFORMATION"), x.get("ADJUSTMENT")) != (freq, medida, transf, ajuste):
                continue
            if x.get("OBS_VALUE") in ("", None):
                continue
            p = x["TIME_PERIOD"]
            quando = pd.Timestamp(int(p[:4]), 3 * int(p[-1]) - 2, 1) if "-Q" in p else pd.Timestamp(p + "-01")
            pontos[quando] = float(x["OBS_VALUE"])
        if pontos:
            saida[k] = {"nome": nome, **_serie(pd.Series(pontos).sort_index(), 2)}
    if "cpi_12m" not in saida or "pib_12m" not in saida:
        raise RuntimeError("OCDE (China): inflação ou PIB ausentes")
    # Séries do NBS sem fonte contínua: espelho do DBnomics (13 meses, parado em fev/2026) — marcadas como descontinuadas
    for k, (serie, nome) in SERIES_NBS_DBNOMICS.items():
        try:
            x = _get(f"https://api.db.nomics.world/v22/series/NBS/{serie}?observations=1", headers=NAVEGADOR).json()["series"]["docs"][0]
            pontos = {pd.Timestamp(p + "-01"): float(v) for p, v in zip(x["period"], x["value"]) if v not in ("NA", None)}
            if pontos:
                saida[k] = {"nome": nome, "descontinuada": True, "fonte": "NBS via DBnomics (13 meses, sem atualização desde fev/2026)",
                            **_serie(pd.Series(pontos).sort_index(), 2)}
        except Exception:  # noqa: BLE001 — opcional: se o espelho sair do ar, a série some e o resto segue
            pass
    return saida


# ---------------- Global (FMI, WEO) ----------------
URL_FMI = "https://www.imf.org/external/datamapper/api/v1/{ind}"
INDICADORES_FMI = {
    "NGDP_RPCH": "Crescimento do PIB real (%)", "PCPIPCH": "Inflação média ao consumidor (%)", "LUR": "Desemprego (%)",
    "GGXWDG_NGDP": "Dívida bruta do governo (% do PIB)", "GGXCNL_NGDP": "Resultado nominal do governo (% do PIB)",
    "BCA_NGDPD": "Conta corrente (% do PIB)",
}
PAISES_FMI = {
    "WEOWORLD": "Mundo", "ADVEC": "Economias avançadas", "OEMDC": "Emergentes e em desenvolvimento",
    "BRA": "Brasil", "USA": "Estados Unidos", "EURO": "Zona do Euro", "CHN": "China", "JPN": "Japão", "DEU": "Alemanha",
    "GBR": "Reino Unido", "FRA": "França", "ITA": "Itália", "CAN": "Canadá", "IND": "Índia", "MEX": "México", "ARG": "Argentina",
    "CHL": "Chile", "COL": "Colômbia", "PER": "Peru", "ZAF": "África do Sul", "KOR": "Coreia do Sul", "IDN": "Indonésia",
    "TUR": "Turquia", "SAU": "Arábia Saudita", "AUS": "Austrália", "RUS": "Rússia",
}


def global_fmi():
    saida = {"paises": PAISES_FMI, "indicadores": {}}
    for ind, nome in INDICADORES_FMI.items():
        # o FMI recusa cabeçalhos de navegador; aceita o identificador padrão da biblioteca requests
        valores = _get(URL_FMI.format(ind=ind), headers={"User-Agent": requests.utils.default_user_agent()}).json().get("values", {}).get(ind, {})
        por_pais = {c: {a: round(float(v), 2) for a, v in valores[c].items() if 2000 <= int(a) <= date.today().year + 5}
                    for c in PAISES_FMI if c in valores}
        if por_pais:
            saida["indicadores"][ind] = {"nome": nome, "valores": por_pais}
    if "NGDP_RPCH" not in saida["indicadores"]:
        raise RuntimeError("FMI: crescimento do PIB ausente")
    # último ano com dado efetivo (não projeção): o WEO de abril projeta o ano corrente
    saida["ano_corrente"] = date.today().year
    return saida


FONTES = {"mercados": ("FRED — mercados", mercados), "commodities": ("Banco Mundial — commodities", commodities),
          "china": ("OCDE — China", china), "global": ("FMI — World Economic Outlook", global_fmi)}


def gerar():
    anterior = json.loads(ARQ.read_text(encoding="utf-8")) if ARQ.exists() else {}
    saida, falhas = {}, []
    for chave, (nome, funcao) in FONTES.items():
        try:
            saida[chave] = funcao()
            falhas += [f"{nome}: {x}" for x in (saida[chave].get("falhas") or [])] if isinstance(saida[chave], dict) else []
        except Exception as e:
            falhas.append(f"{nome}: {e!r}"[:300])
            if chave in anterior:
                saida[chave] = anterior[chave]
    falhas = [sem_segredos(f) for f in falhas]
    ARQ.write_text(json.dumps({"gerado_em": datetime.now(FUSO_BR).isoformat(timespec="minutes"), **saida, "falhas": falhas},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"✅ mundo: {', '.join(saida)}; falhas: {falhas or 'nenhuma'} ({ARQ.stat().st_size // 1024} KB)")
    if not saida:
        raise RuntimeError("nenhuma fonte do Mundo respondeu")
    return ARQ


if __name__ == "__main__":
    gerar()
