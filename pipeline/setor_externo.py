"""
Setor externo do Brasil (Macro → Setor externo):

- Banco Central (SGS, balanço de pagamentos BPM6, mensal, US$ milhões): transações correntes, investimento
  direto no país (IDP), investimento estrangeiro em carteira (ações e títulos), balança comercial do balanço
  de pagamentos e reservas internacionais (conceito liquidez, diária). Códigos conferidos no catálogo de
  dados abertos do BC.
- Comex Stat (Ministério do Desenvolvimento, Indústria, Comércio e Serviços, API oficial): exportações e
  importações mensais (FOB, US$), exportações por produto (posições do Sistema Harmonizado) e por destino.

Cada parte que falhar fica com a versão anterior. Saída: site/dados/setor_externo.json.
Uso: py -m pipeline.setor_externo
"""

import json
import time
from datetime import date, datetime

import pandas as pd
import requests

from pipeline import DIR_DADOS_SITE, sem_segredos
from pipeline.macro import _empacotar, _regrediu, baixar_sgs

ARQ = DIR_DADOS_SITE / "setor_externo.json"
SERIES_BC = {
    "tc_mensal": (22701, "Transações correntes — saldo mensal", "US$ milhões"),
    "tc_12m": (24419, "Transações correntes — acumulado em 12 meses", "US$ milhões"),
    "tc_pib": (23079, "Transações correntes — 12 meses em % do PIB", "% PIB"),
    "idp_mensal": (22885, "Investimento direto no país (IDP) — líquido no mês", "US$ milhões"),
    "carteira_mensal": (22924, "Investimento estrangeiro em carteira — líquido no mês", "US$ milhões"),
    "carteira_acoes": (22927, "Investimento estrangeiro em ações — líquido no mês", "US$ milhões"),
    "carteira_titulos": (22939, "Investimento estrangeiro em títulos de dívida — líquido no mês", "US$ milhões"),
    "bp_exportacoes": (22708, "Exportação de bens (balanço de pagamentos)", "US$ milhões"),
    "bp_importacoes": (22709, "Importação de bens (balanço de pagamentos)", "US$ milhões"),
    "reservas": (13982, "Reservas internacionais — conceito liquidez", "US$ milhões"),
}

URL_COMEX = "https://api-comexstat.mdic.gov.br/general?language=pt"
# Produtos que movem as empresas da B3 (posição de 4 dígitos do Sistema Harmonizado)
PRODUTOS = {
    "2601": "Minério de ferro", "2709": "Petróleo bruto", "1201": "Soja em grão", "2304": "Farelo de soja", "1005": "Milho",
    "0202": "Carne bovina congelada", "0207": "Carne de frango", "4703": "Celulose", "1701": "Açúcar", "0901": "Café",
    "5201": "Algodão", "7207": "Aço semiacabado", "8802": "Aviões", "2710": "Derivados de petróleo",
}
DESTINOS = ["China", "Estados Unidos", "Argentina", "Países Baixos (Holanda)", "Espanha", "Singapura", "Índia", "Chile", "México", "Japão"]
INICIO_COMEX = 2015


def _comex(corpo, tentativas=4):
    for i in range(tentativas):
        try:
            r = requests.post(URL_COMEX, json=corpo, timeout=120, headers={"Content-Type": "application/json"})
            if r.status_code == 429:
                raise requests.HTTPError("HTTP 429 (limite de consultas)")
            r.raise_for_status()
            return r.json()["data"]["list"]
        except (requests.RequestException, ValueError, KeyError) as e:
            if i == tentativas - 1:
                raise RuntimeError(f"Comex Stat: {e}") from None
            time.sleep(10 * (i + 1))


def _serie_mensal(lista, campo="metricFOB"):
    pontos = {}
    for x in lista:
        d = pd.Timestamp(int(x["year"]), int(x["monthNumber"]), 1)
        pontos[d] = pontos.get(d, 0.0) + float(x[campo])
    return pd.Series(pontos).sort_index()


def comex():
    hoje = date.today()
    # A API aplica o intervalo de meses a cada ano (de jan/2015 a out/2026 = só janeiro a outubro de todos os anos):
    # por isso o período vai até dezembro do ano corrente (meses ainda não divulgados simplesmente não vêm)
    periodo = {"from": f"{INICIO_COMEX}-01", "to": f"{hoje.year}-12"}
    saida = {}
    for fluxo in ("export", "import"):
        s = _serie_mensal(_comex({"flow": fluxo, "monthDetail": True, "period": periodo, "filters": [], "details": [], "metrics": ["metricFOB"]}))
        saida[{"export": "exportacoes", "import": "importacoes"}[fluxo]] = _empacotar(s / 1e6, f"{'Exportações' if fluxo == 'export' else 'Importações'} (FOB)", "US$ milhões", casas=1)
        time.sleep(2)
    lista = _comex({"flow": "export", "monthDetail": True, "period": periodo, "filters": [{"filter": "heading", "values": list(PRODUTOS)}],
                    "details": ["heading"], "metrics": ["metricFOB"]})
    produtos = {}
    for cod, nome in PRODUTOS.items():
        s = _serie_mensal([x for x in lista if x.get("headingCode") == cod])
        if not s.empty:
            produtos[cod] = {**_empacotar(s / 1e6, nome, "US$ milhões", casas=1), "codigo": cod}
    saida["produtos"] = produtos
    time.sleep(2)
    lista = _comex({"flow": "export", "monthDetail": True, "period": periodo, "filters": [], "details": ["country"], "metrics": ["metricFOB"]})
    destinos = {}
    for pais in DESTINOS:
        s = _serie_mensal([x for x in lista if x.get("country") == pais])
        if not s.empty:
            destinos[pais] = _empacotar(s / 1e6, pais, "US$ milhões", casas=1)
    time.sleep(2)
    blocos = _comex({"flow": "export", "monthDetail": True, "period": periodo, "filters": [], "details": ["economicBlock"], "metrics": ["metricFOB"]})
    ue = _serie_mensal([x for x in blocos if "Europeia" in (x.get("economicBlock") or "")])
    if not ue.empty:
        destinos["União Europeia"] = _empacotar(ue / 1e6, "União Europeia", "US$ milhões", casas=1)
    saida["destinos"] = destinos
    if "exportacoes" not in saida or len(produtos) < 8:
        raise RuntimeError("Comex Stat: resposta incompleta")
    return saida


def banco_central(anteriores):
    saida, falhas = {}, []
    for chave, (cod, nome, un) in SERIES_BC.items():
        try:
            diaria = chave == "reservas"
            nova = baixar_sgs(cod, inicio=2000, janela=10 if diaria else 30)
            if diaria:  # reservas: posição no fim de cada mês
                nova = nova.resample("MS").last().dropna()
            problema = _regrediu(nova, (anteriores or {}).get(chave))
            if problema:
                raise RuntimeError(problema)
            saida[chave] = _empacotar(nova, nome, un, casas=1)
        except Exception as e:  # noqa: BLE001
            falhas.append(f"{chave} (SGS {cod}): {e}"[:200])
            if anteriores and chave in anteriores:
                saida[chave] = anteriores[chave]
    # IDP e carteira em 12 meses; IDP em % do PIB pelo PIB em dólares implícito nas transações correntes (TC 12m ÷ TC % PIB)
    def ser(k):
        return pd.Series(saida[k]["valores"], index=pd.to_datetime(saida[k]["datas"]), dtype=float) if k in saida else None
    for k, nome in (("idp_mensal", "Investimento direto no país — 12 meses"), ("carteira_mensal", "Investimento estrangeiro em carteira — 12 meses"),
                    ("carteira_acoes", "Investimento estrangeiro em ações — 12 meses")):
        s = ser(k)
        if s is not None:
            saida[k.replace("_mensal", "") + "_12m" if k.endswith("_mensal") else f"{k}_12m"] = _empacotar(s.rolling(12).sum().dropna(), nome, "US$ milhões", casas=1)
    tc12, tcpib, idp12 = ser("tc_12m"), ser("tc_pib"), ser("idp_12m") if "idp_12m" in saida else None
    if tc12 is not None and tcpib is not None and idp12 is not None:
        pib_usd = (tc12 / (tcpib / 100)).replace([float("inf"), -float("inf")], float("nan"))
        saida["idp_pib"] = _empacotar((idp12 / pib_usd * 100).dropna(), "Investimento direto no país — 12 meses em % do PIB", "% PIB", casas=2)
    return saida, falhas


def gerar():
    anterior = json.loads(ARQ.read_text(encoding="utf-8")) if ARQ.exists() else {}
    falhas = []
    bc, f = banco_central(anterior.get("bc"))
    falhas += f
    try:
        cx = comex()
    except Exception as e:  # noqa: BLE001
        falhas.append(f"Comex Stat: {e}"[:200])
        cx = anterior.get("comex", {})
    if not bc and not cx:
        raise RuntimeError("nenhuma fonte do setor externo respondeu")
    falhas = [sem_segredos(x) for x in falhas]
    ARQ.write_text(json.dumps({"gerado_em": datetime.now().isoformat(timespec="minutes"), "bc": bc, "comex": cx, "falhas": falhas},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ult = (cx.get("exportacoes") or {}).get("datas", ["—"])[-1]
    print(f"✅ setor externo: {len(bc)} séries do BC; Comex até {ult}; {len(falhas)} falhas")
    for x in falhas:
        print("   ⚠️", x)
    return ARQ


if __name__ == "__main__":
    gerar()
