"""
Títulos públicos do Tesouro Direto (dados abertos do Tesouro Transparente):
curvas prefixada e IPCA+ em 5 datas, inflação implícita e histórico de taxa/preço
de cada título à venda -> site/dados/tesouro.json e site/dados/tesouro/{id}.json
"""

import json
import re
import unicodedata
from datetime import date

import pandas as pd
import requests

from config.config import RAW_DIR
from pipeline import DIR_DADOS_SITE

URL = ("https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/"
       "resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv")
ARQ = RAW_DIR / "tesouro_precos_taxas.csv"
DIR_TITULOS = DIR_DADOS_SITE / "tesouro"

PREFIXADO = ("Tesouro Prefixado", "Tesouro Prefixado com Juros Semestrais")
IPCA = ("Tesouro IPCA+", "Tesouro IPCA+ com Juros Semestrais")
DATAS_REFERENCIA = {"hoje": 0, "1 semana": 7, "1 mês": 30, "6 meses": 182, "1 ano": 365}


def baixar():
    with requests.get(URL, timeout=300, stream=True) as r:
        r.raise_for_status()
        with open(ARQ, "wb") as f:
            for parte in r.iter_content(chunk_size=1 << 20):
                f.write(parte)


def carregar():
    d = pd.read_csv(ARQ, sep=";", decimal=",")
    d["Data Base"] = pd.to_datetime(d["Data Base"], dayfirst=True)
    d["Data Vencimento"] = pd.to_datetime(d["Data Vencimento"], dayfirst=True)
    return d.sort_values(["Tipo Titulo", "Data Vencimento", "Data Base"])


def _slug(tipo, vencimento):
    texto = unicodedata.normalize("NFKD", f"{tipo} {vencimento:%Y}").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", texto.lower().replace("+", " mais ")).strip("-") + f"-{vencimento:%m%d}"


def _curva(dia, tipos):
    """Pontos (anos até o vencimento, taxa): título sem cupom primeiro, com cupom só onde ele não chega."""
    zero = dia[dia["Tipo Titulo"] == tipos[0]]
    cupom = dia[dia["Tipo Titulo"] == tipos[1]]
    if not zero.empty:
        cupom = cupom[cupom["Data Vencimento"] > zero["Data Vencimento"].max()]
    pontos = pd.concat([zero, cupom]).sort_values("Data Vencimento")
    pontos = pontos[pontos["Taxa Compra Manha"] > 0]
    base = dia["Data Base"].iloc[0]
    return [
        {"vencimento": v.strftime("%Y-%m-%d"), "anos": round((v - base).days / 365.25, 3),
         "taxa": float(t), "titulo": tipo}
        for v, t, tipo in zip(pontos["Data Vencimento"], pontos["Taxa Compra Manha"], pontos["Tipo Titulo"])
    ]


def _inflacao_implicita(pre, ipca):
    """Em cada vencimento IPCA+, interpola a taxa prefixada (sem extrapolar) e compara."""
    if len(pre) < 2:
        return []
    xs, ys = [p["anos"] for p in pre], [p["taxa"] for p in pre]
    saida = []
    for p in ipca:
        if not xs[0] <= p["anos"] <= xs[-1]:
            continue
        i = next(k for k in range(1, len(xs)) if xs[k] >= p["anos"])
        frac = (p["anos"] - xs[i - 1]) / (xs[i] - xs[i - 1]) if xs[i] != xs[i - 1] else 0
        taxa_pre = ys[i - 1] + frac * (ys[i] - ys[i - 1])
        saida.append({"vencimento": p["vencimento"], "anos": p["anos"],
                      "taxa": round(((1 + taxa_pre / 100) / (1 + p["taxa"] / 100) - 1) * 100, 4)})
    return saida


def gerar(baixar_arquivo=True):
    if baixar_arquivo or not ARQ.exists():
        baixar()
    d = carregar()
    ultima = d["Data Base"].max()
    datas_disponiveis = sorted(d["Data Base"].unique())

    curvas = {}
    for rotulo, dias in DATAS_REFERENCIA.items():
        alvo = ultima - pd.Timedelta(days=dias)
        dia_ref = max(x for x in datas_disponiveis if x <= alvo)
        dia = d[d["Data Base"] == dia_ref]
        pre, ipca = _curva(dia, PREFIXADO), _curva(dia, IPCA)
        curvas[rotulo] = {"data": pd.Timestamp(dia_ref).strftime("%Y-%m-%d"), "prefixado": pre, "ipca": ipca,
                          "inflacao_implicita": _inflacao_implicita(pre, ipca)}

    DIR_TITULOS.mkdir(parents=True, exist_ok=True)
    titulos = []
    ativos = d[d["Data Vencimento"] > ultima]
    for (tipo, venc), hist in ativos.groupby(["Tipo Titulo", "Data Vencimento"]):
        if hist["Data Base"].max() < ultima:
            continue  # não está mais à venda
        id_ = _slug(tipo, venc)
        hist = hist.drop_duplicates("Data Base", keep="last")
        (DIR_TITULOS / f"{id_}.json").write_text(json.dumps({
            "id": id_, "tipo": tipo, "vencimento": venc.strftime("%Y-%m-%d"),
            "datas": hist["Data Base"].dt.strftime("%Y-%m-%d").tolist(),
            "taxa_compra": hist["Taxa Compra Manha"].round(4).tolist(),
            "taxa_venda": hist["Taxa Venda Manha"].round(4).tolist(),
            "pu_compra": hist["PU Compra Manha"].round(2).tolist(),
            "pu_venda": hist["PU Venda Manha"].round(2).tolist(),
        }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        ult = hist.iloc[-1]
        titulos.append({"id": id_, "tipo": tipo, "vencimento": venc.strftime("%Y-%m-%d"),
                        "taxa_compra": float(ult["Taxa Compra Manha"]), "pu_compra": float(ult["PU Compra Manha"])})

    arquivo = DIR_DADOS_SITE / "tesouro.json"
    arquivo.write_text(json.dumps({
        "gerado_em": date.today().isoformat(), "data_base": ultima.strftime("%Y-%m-%d"),
        "curvas": curvas, "titulos": titulos,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return arquivo


if __name__ == "__main__":
    caminho = gerar(baixar_arquivo=not ARQ.exists())
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    for rotulo, c in dados["curvas"].items():
        print(f"{rotulo:9s} {c['data']}  pré {len(c['prefixado'])} pts ({c['prefixado'][0]['taxa']}%→{c['prefixado'][-1]['taxa']}%)"
              f"  IPCA+ {len(c['ipca'])} pts  implícita {[x['taxa'] for x in c['inflacao_implicita']][:3]}")
    print(len(dados["titulos"]), "títulos à venda;", caminho.stat().st_size // 1024, "KB")
