"""
Títulos públicos do Tesouro Direto: curvas prefixada e IPCA+ em 5 datas, inflação implícita
e histórico de taxa/preço de cada título à venda -> site/dados/tesouro.json e site/dados/tesouro/{id}.json

- Histórico: dados abertos do Tesouro Transparente (um registro por dia, publicado com 1–2 dias de atraso).
- Tempo real (não oficial): taxas e preços que o site do Tesouro Direto mostra no momento (repreçados
  ao longo do dia), num bloco separado ("tempo_real") que nunca altera os dados oficiais. Endereço
  interno do site, sem documentação; passa por travas (LIMITE_SALTO) antes de ser publicado.

Uso: py -m pipeline.tesouro [--intradia]   (--intradia reaproveita o CSV já baixado)
"""

import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from config.config import RAW_DIR
from pipeline import DIR_DADOS_SITE

URL = ("https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/"
       "resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv")
# Metadados do mesmo arquivo (poucos bytes): a data da última publicação evita baixar os ~15 MB sem necessidade
URL_METADADOS = ("https://www.tesourotransparente.gov.br/ckan/api/3/action/resource_show"
                 "?id=796d2059-14e9-44e3-80c9-2d9e30b405c1")
ARQ = RAW_DIR / "tesouro_precos_taxas.csv"
ARQ_VERSAO = RAW_DIR / "tesouro_precos_taxas.versao"  # last_modified do arquivo baixado
DIR_TITULOS = DIR_DADOS_SITE / "tesouro"
FUSO_BR = timezone(timedelta(hours=-3))

PREFIXADO = ("Tesouro Prefixado", "Tesouro Prefixado com Juros Semestrais")
IPCA = ("Tesouro IPCA+", "Tesouro IPCA+ com Juros Semestrais")
URL_AO_VIVO = "https://www.tesourodireto.com.br/o/rentabilidade/investir"
CABECALHO = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36",
             "Accept": "application/json"}
LIMITE_SALTO = 1.0  # pontos percentuais entre a taxa do momento e a última taxa oficial do título
DATAS_REFERENCIA = {"hoje": 0, "1 semana": 7, "1 mês": 30, "6 meses": 182, "1 ano": 365}


def versao_publicada():
    """Data e hora da última publicação do arquivo no Tesouro Transparente."""
    r = requests.get(URL_METADADOS, headers=CABECALHO, timeout=60)
    r.raise_for_status()
    return r.json()["result"]["last_modified"]


def baixar():
    """Baixa o arquivo só quando o Tesouro publicou uma versão nova.

    O servidor recusa pedidos em excesso (HTTP 429): com uma cópia anterior, a falha não derruba a etapa
    e volta como aviso (o monitor acusa se os dados ficarem parados). Devolve o aviso ou None."""
    try:
        versao = versao_publicada()
    except (requests.RequestException, ValueError, KeyError) as e:
        if ARQ.exists():
            return f"data da publicação indisponível ({type(e).__name__}); mantido o arquivo anterior"
        versao = None
    if versao and ARQ.exists() and ARQ_VERSAO.exists() and ARQ_VERSAO.read_text(encoding="utf-8") == versao:
        return None
    if versao and ARQ.exists() and not ARQ_VERSAO.exists():
        # cópia anterior a este controle: se foi baixada depois da publicação, já é a versão atual
        publicado = datetime.fromisoformat(versao[:19]).replace(tzinfo=timezone.utc)
        if datetime.fromtimestamp(ARQ.stat().st_mtime, timezone.utc) > publicado:
            ARQ_VERSAO.write_text(versao, encoding="utf-8")
            return None
    parcial = ARQ.with_suffix(".parcial")  # o arquivo anterior só é trocado depois do download completo
    try:
        with requests.get(URL, timeout=300, stream=True) as r:
            r.raise_for_status()
            with open(parcial, "wb") as f:
                for parte in r.iter_content(chunk_size=1 << 20):
                    f.write(parte)
        parcial.replace(ARQ)
    except requests.RequestException as e:
        parcial.unlink(missing_ok=True)
        if not ARQ.exists():
            raise
        return f"arquivo novo não baixado ({type(e).__name__}); mantida a versão anterior"
    if versao:
        ARQ_VERSAO.write_text(versao, encoding="utf-8")
    return None


def carregar():
    d = pd.read_csv(ARQ, sep=";", decimal=",")
    d["Data Base"] = pd.to_datetime(d["Data Base"], dayfirst=True)
    d["Data Vencimento"] = pd.to_datetime(d["Data Vencimento"], dayfirst=True)
    return d.sort_values(["Tipo Titulo", "Data Vencimento", "Data Base"])


def _taxa(texto):
    """'IPCA + 6,86%' -> 6.86; '12,83%' -> 12.83; 'SELIC + 0,0988%' -> 0.0988."""
    m = re.search(r"(-?\d+(?:,\d+)?)\s*%", texto or "")
    return float(m.group(1).replace(",", ".")) if m else None


def ao_vivo():
    """Taxas e preços do momento no site do Tesouro Direto, por (tipo, vencimento).

    O nome do Educa+ e do Renda+ traz o ano do início dos pagamentos, não o do vencimento:
    por isso o casamento com o Tesouro Transparente é pelo tipo e pela data de vencimento."""
    d = requests.get(URL_AO_VIVO, headers=CABECALHO, timeout=60).json()
    saida = {}
    for t in d.get("TesouroLegado", []):
        tipo = re.sub(r"\s+\d{4}$", "", t["treasuryBondName"].strip())
        saida[(tipo, (t.get("maturityDate") or "")[:10])] = {
            "taxa_compra": _taxa(t.get("investmentProfitabilityIndexerName")), "pu_compra": t.get("unitaryInvestmentValue"),
            "taxa_venda": _taxa(t.get("redemptionProfitabilityFeeIndexerName")), "pu_venda": t.get("unitaryRedemptionValue"),
            "precificado_em": (t.get("lastMarketPricingDate") or "")[:16],
        }
    if not saida:
        raise ValueError("Tesouro Direto não devolveu títulos")
    return saida


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


def _interpolar(curva, anos):
    """Taxa da curva no prazo (interpolação linear entre vencimentos), ou None fora da faixa — nunca extrapola."""
    xs, ys = [p["anos"] for p in curva], [p["taxa"] for p in curva]
    if len(xs) < 2 or not xs[0] <= anos <= xs[-1]:
        return None
    i = next(k for k in range(1, len(xs)) if xs[k] >= anos)
    frac = (anos - xs[i - 1]) / (xs[i] - xs[i - 1]) if xs[i] != xs[i - 1] else 0
    return ys[i - 1] + frac * (ys[i] - ys[i - 1])


def _inflacao_implicita(pre, ipca):
    """
    Em cada vencimento IPCA+ e em cada vencimento prefixado dentro da faixa em que as duas curvas existem,
    interpola a outra curva (sem extrapolar) e calcula (1 + pré) ÷ (1 + real) − 1.
    """
    if len(pre) < 2 or len(ipca) < 2:
        return []
    pontos = {}
    for p in ipca:
        taxa_pre = _interpolar(pre, p["anos"])
        if taxa_pre is not None:
            pontos[p["anos"]] = (p["vencimento"], taxa_pre, p["taxa"], "IPCA+")
    for p in pre:
        taxa_real = _interpolar(ipca, p["anos"])
        if taxa_real is not None and p["anos"] not in pontos:
            pontos[p["anos"]] = (p["vencimento"], p["taxa"], taxa_real, "prefixado")
    return [{"vencimento": venc, "anos": anos, "base": base,
             "taxa": round(((1 + tp / 100) / (1 + tr / 100) - 1) * 100, 4)}
            for anos, (venc, tp, tr, base) in sorted(pontos.items())]


def gerar(baixar_arquivo=True):
    aviso_oficial = baixar() if baixar_arquivo or not ARQ.exists() else None
    if aviso_oficial:
        print("   ⚠️ Tesouro Transparente:", aviso_oficial)
    d = carregar()
    ultima = d["Data Base"].max()
    datas_disponiveis = sorted(d["Data Base"].unique())
    vivo, falha_ao_vivo = {}, None
    try:
        vivo = ao_vivo()
    except Exception as e:  # sem o preço do momento, fica o último dia do Tesouro Transparente
        falha_ao_vivo = repr(e)[:200]
        print("   ⚠️ Tesouro Direto ao vivo indisponível:", falha_ao_vivo)
    # Travas: só vale o preço do momento mais novo que o último dia oficial, com PU positivo e taxa a no
    # máximo LIMITE_SALTO pontos da última taxa oficial do mesmo título; o resto é descartado e registrado
    oficiais = d[d["Data Base"] == ultima].set_index(["Tipo Titulo", d.loc[d["Data Base"] == ultima, "Data Vencimento"].dt.strftime("%Y-%m-%d")])
    aceitos, descartados = {}, []
    for (tipo, venc), v in vivo.items():
        if v["taxa_compra"] is None or v["precificado_em"][:10] <= f"{ultima:%Y-%m-%d}" or (tipo, venc) not in oficiais.index:
            continue
        taxa_oficial = float(oficiais.loc[(tipo, venc), "Taxa Compra Manha"])
        if not (v["pu_compra"] or 0) > 0 or abs(v["taxa_compra"] - taxa_oficial) > LIMITE_SALTO:
            descartados.append(f"{tipo} {venc}: {v['taxa_compra']}% (oficial {taxa_oficial}%), PU {v['pu_compra']}")
            continue
        aceitos[(tipo, venc)] = v
    vivo = aceitos
    if descartados:
        falha_ao_vivo = "preços descartados pelas travas: " + "; ".join(descartados)[:400]
        print("   ⚠️", falha_ao_vivo)
    precificado_em = max((v["precificado_em"] for v in vivo.values()), default=None)

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

    # Tempo real (não oficial): bloco separado; não altera curvas, títulos nem histórico oficiais
    agora = None
    if vivo:
        dia = d[d["Data Base"] == ultima].copy()
        chave = list(zip(dia["Tipo Titulo"], dia["Data Vencimento"].dt.strftime("%Y-%m-%d")))
        dia["Taxa Compra Manha"] = [vivo[k]["taxa_compra"] if k in vivo else None for k in chave]
        dia = dia.dropna(subset=["Taxa Compra Manha"])
        dia["Data Base"] = pd.Timestamp(precificado_em[:10])
        pre, ipca = _curva(dia, PREFIXADO), _curva(dia, IPCA)
        agora = {
            "precificado_em": precificado_em, "fonte": "site do Tesouro Direto (não oficial, sem documentação)",
            "curva": {"prefixado": pre, "ipca": ipca, "inflacao_implicita": _inflacao_implicita(pre, ipca)},
            "titulos": [{"id": _slug(tipo, pd.Timestamp(venc)), "tipo": tipo, "vencimento": venc, **v} for (tipo, venc), v in sorted(vivo.items())],
        }

    arquivo = DIR_DADOS_SITE / "tesouro.json"
    arquivo.write_text(json.dumps({
        "gerado_em": datetime.now(FUSO_BR).isoformat(timespec="minutes"),
        "fonte": "Tesouro Transparente (dados abertos oficiais)", "data_base": ultima.strftime("%Y-%m-%d"),
        "publicado_em": ARQ_VERSAO.read_text(encoding="utf-8") if ARQ_VERSAO.exists() else None,
        "aviso_oficial": aviso_oficial, "curvas": curvas, "titulos": titulos, "tempo_real": agora, "falha_tempo_real": falha_ao_vivo,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return arquivo


if __name__ == "__main__":
    caminho = gerar()
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    for rotulo, c in dados["curvas"].items():
        print(f"{rotulo:9s} {c['data']}  pré {len(c['prefixado'])} pts ({c['prefixado'][0]['taxa']}%→{c['prefixado'][-1]['taxa']}%)"
              f"  IPCA+ {len(c['ipca'])} pts  implícita {[x['taxa'] for x in c['inflacao_implicita']][:3]}")
    tr = dados["tempo_real"]
    print(len(dados["titulos"]), "títulos (oficial, referência", dados["data_base"] + ");",
          f"tempo real: {len(tr['titulos'])} títulos às {tr['precificado_em']}" if tr else f"tempo real indisponível ({dados['falha_tempo_real']})",
          ";", caminho.stat().st_size // 1024, "KB")
