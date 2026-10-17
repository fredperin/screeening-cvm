"""
Séries macroeconômicas do Banco Central (API SGS) e expectativas do boletim
Focus (API Olinda) para a seção Macro do site -> site/dados/macro.json
"""

import json
import time
from datetime import date
from urllib.parse import quote

import pandas as pd
import requests

from pipeline import DIR_DADOS_SITE

URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial={ini}&dataFinal={fim}"
URL_FOCUS = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais"
INICIO = 2000

SERIES = {
    "ipca": (433, "IPCA (mensal)", "% a.m."),
    "igpm": (189, "IGP-M (mensal)", "% a.m."),
    "selic_meta": (432, "Selic meta", "% a.a."),
    "cdi": (4389, "CDI anualizado", "% a.a."),
    "usd": (1, "Dólar PTAX (venda)", "R$"),
    "eur": (21619, "Euro PTAX (venda)", "R$"),
    "pib_anual": (7326, "PIB, variação real anual", "%"),
    "pib_indice": (22109, "PIB trimestral, índice dessazonalizado", "índice"),
    "pib_indice_obs": (22099, "PIB trimestral, índice observado (sem ajuste)", "índice"),
    "ibcbr": (24363, "IBC-Br, índice observado (sem ajuste)", "índice"),
    "ibcbr_dessaz": (24364, "IBC-Br, índice dessazonalizado", "índice"),
}
FOCUS = {"ipca": "IPCA", "selic": "Selic", "cambio": "Câmbio", "pib": "PIB Total"}


def _get(url, params=None, tentativas=4):
    for i in range(tentativas):
        try:
            r = requests.get(url, params=params, timeout=60)
            if r.status_code == 404:
                return []
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError):
            if i == tentativas - 1:
                raise
            time.sleep(2 * (i + 1))


def baixar_sgs(codigo):
    """Série completa desde 2000, em janelas de 10 anos (limite da API para séries diárias)."""
    partes, hoje = [], date.today()
    for ano in range(INICIO, hoje.year + 1, 10):
        ini, fim = date(ano, 1, 1), min(date(ano + 9, 12, 31), hoje)
        dados = _get(URL_SGS.format(codigo=codigo, ini=ini.strftime("%d/%m/%Y"), fim=fim.strftime("%d/%m/%Y")))
        partes.extend(dados)
    if not partes:
        return pd.Series(dtype=float)
    df = pd.DataFrame(partes)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    serie = pd.to_numeric(df["valor"], errors="coerce").set_axis(df["data"])
    serie = serie[~serie.index.duplicated(keep="last")].sort_index()
    return serie[serie.index <= pd.Timestamp(hoje)].dropna()


def acumulado_12m(mensal):
    return ((1 + mensal / 100).rolling(12).apply(lambda x: x.prod(), raw=True) - 1) * 100


def _empacotar(serie, nome, unidade, casas=4):
    return {
        "nome": nome, "unidade": unidade,
        "datas": [d.strftime("%Y-%m-%d") for d in serie.index],
        "valores": [round(float(v), casas) for v in serie.values],
    }


def baixar_focus(indicador, todos_os_anos=False):
    """Mediana diária das expectativas (ano corrente e seguinte, ou todos os anos projetados), desde 2 anos atrás."""
    hoje = date.today()
    filtro = (f"Indicador eq '{indicador}' and baseCalculo eq 0 and Data ge '{hoje.year - 2}-01-01'")
    # O Olinda rejeita espaço codificado como "+" (padrão do requests): monta a URL com %20
    url = (f"{URL_FOCUS}?$filter={quote(filtro)}&$select=Data,DataReferencia,Mediana"
           f"&$format=json&$top=100000")
    dados = _get(url)
    df = pd.DataFrame(dados.get("value", []) if isinstance(dados, dict) else [])
    saida = {}
    anos = sorted({int(a) for a in df["DataReferencia"].unique() if str(a).isdigit() and int(a) >= hoje.year})         if todos_os_anos and not df.empty else (hoje.year, hoje.year + 1)
    for ano in anos:
        sub = df[df["DataReferencia"] == str(ano)].sort_values("Data") if not df.empty else df
        if sub.empty:
            continue
        sub = sub.drop_duplicates("Data", keep="last")
        saida[str(ano)] = {"datas": sub["Data"].tolist(), "valores": [round(float(v), 4) for v in sub["Mediana"]]}
    return saida


def gerar():
    brutas = {chave: baixar_sgs(codigo) for chave, (codigo, _, _) in SERIES.items()}
    # A Selic meta só muda nas reuniões do Copom: guarda só os pontos de mudança (gráfico em degraus)
    selic = brutas["selic_meta"]
    brutas["selic_meta"] = pd.concat([selic[selic.diff() != 0], selic.iloc[[-1]]]).pipe(lambda s: s[~s.index.duplicated()])
    saida = {chave: _empacotar(brutas[chave], nome, un) for chave, (_, nome, un) in SERIES.items()}

    saida["ipca_12m"] = _empacotar(acumulado_12m(brutas["ipca"]).dropna(), "IPCA acumulado em 12 meses", "%")
    saida["igpm_12m"] = _empacotar(acumulado_12m(brutas["igpm"]).dropna(), "IGP-M acumulado em 12 meses", "%")

    pib = brutas["pib_indice"]
    saida["pib_tri"] = _empacotar(((pib / pib.shift(1) - 1) * 100).dropna(), "PIB, variação trimestral dessazonalizada", "%")

    # Juro real ex-post: Selic meta no fim de cada mês descontado do IPCA 12 meses
    selic_mes = brutas["selic_meta"].resample("MS").last()
    ipca12 = acumulado_12m(brutas["ipca"])
    juntos = pd.concat([selic_mes, ipca12], axis=1, keys=["selic", "ipca"]).dropna()
    real = ((1 + juntos["selic"] / 100) / (1 + juntos["ipca"] / 100) - 1) * 100
    saida["juro_real"] = _empacotar(real, "Juro real ex-post (Selic meta ÷ IPCA 12m)", "% a.a.")

    # Acumulado em 4 trimestres (como o IBGE divulga): soma dos últimos 4 trimestres sobre os 4 anteriores
    obs = brutas["pib_indice_obs"]
    saida["pib_12m"] = _empacotar(((obs.rolling(4).sum() / obs.rolling(4).sum().shift(4) - 1) * 100).dropna(),
                                  "PIB acumulado em 4 trimestres (12 meses)", "%")
    ibc = brutas["ibcbr_dessaz"]
    saida["ibcbr_mensal"] = _empacotar(((ibc / ibc.shift(1) - 1) * 100).dropna(), "IBC-Br, variação mensal dessazonalizada", "%")
    ibc_obs = brutas["ibcbr"]
    saida["ibcbr_12m"] = _empacotar(((ibc_obs.rolling(12).sum() / ibc_obs.rolling(12).sum().shift(12) - 1) * 100).dropna(),
                                    "IBC-Br acumulado em 12 meses", "%")

    focus = {chave: baixar_focus(nome, todos_os_anos=(chave == "selic")) for chave, nome in FOCUS.items()}
    arquivo = DIR_DADOS_SITE / "macro.json"
    arquivo.write_text(json.dumps({"gerado_em": date.today().isoformat(), "series": saida, "focus": focus},
                                  ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return arquivo


if __name__ == "__main__":
    caminho = gerar()
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    for k, s in dados["series"].items():
        print(f"{k:12s} {len(s['datas']):6d} pontos  último {s['datas'][-1] if s['datas'] else '-'} = {s['valores'][-1] if s['valores'] else '-'} {s['unidade']}")
    for k, f in dados["focus"].items():
        print("focus", k, {ano: (v["datas"][-1], v["valores"][-1]) for ano, v in f.items()})
    print(f"{caminho} ({caminho.stat().st_size // 1024} KB)")
