"""
Monitor de fontes da R.V. Mapp (sem IA, roda no GitHub Actions depois da atualização).

Para cada fonte confere três coisas: respondeu, veio no formato esperado e o dado é
recente. Grava site/dados/saude.json e, se algo estiver errado, data/pipeline/alerta.md
(o workflow transforma esse arquivo numa issue no GitHub, que chega por e-mail).

Uso: py -m pipeline.monitor
"""

import base64
import json
import sys
from datetime import date, datetime, timedelta

import requests

from pipeline import DIR_DADOS_SITE, DIR_INTERMEDIARIO

CABECALHO = {"User-Agent": "Mozilla/5.0"}
ARQ_ALERTA = DIR_INTERMEDIARIO / "alerta.md"


def _b64(obj):
    return base64.b64encode(json.dumps(obj).encode()).decode()


def _dias(data_iso):
    return (date.today() - date.fromisoformat(data_iso[:10])).days


def checar_cvm():
    ano = date.today().year
    r = requests.head(f"https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{ano}.zip", timeout=60)
    r.raise_for_status()
    tamanho = int(r.headers.get("Content-Length", 0))
    assert tamanho > 1_000_000, f"ZIP do ITR {ano} pequeno demais ({tamanho} bytes)"
    modificado = r.headers.get("Last-Modified", "")
    return f"ITR {ano} disponível ({tamanho // 1_000_000} MB, atualizado {modificado})"


def checar_cvm_ipe_fre():
    ano = date.today().year
    saida = []
    for nome, url in (("IPE", f"https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{ano}.zip"),
                      ("FRE", f"https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/fre_cia_aberta_{ano}.zip")):
        r = requests.head(url, timeout=60)
        r.raise_for_status()
        saida.append(f"{nome} {int(r.headers.get('Content-Length', 0)) // 1_000_000} MB")
    return ", ".join(saida)


def checar_cvm_cadastro():
    r = requests.get("https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv", timeout=60, stream=True)
    r.raise_for_status()
    cabecalho = next(r.iter_lines()).decode("latin1")
    for coluna in ("CNPJ_CIA", "DENOM_SOCIAL", "SETOR_ATIV"):
        assert coluna in cabecalho, f"coluna {coluna} sumiu do cadastro"
    return "cadastro com as colunas esperadas"


def checar_b3_empresa():
    url = ("https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/GetListedSupplementCompany/"
           + _b64({"issuingCompany": "WEGE", "language": "pt-br"}))
    d = requests.get(url, headers=CABECALHO, timeout=30).json()[0]
    for campo in ("numberCommonShares", "cashDividends", "tradingName"):
        assert campo in d, f"campo {campo} sumiu"
    return f"WEGE: {d['numberCommonShares']} ações ON"


def checar_b3_proventos():
    url = ("https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/GetListedCashDividends/"
           + _b64({"language": "pt-br", "pageNumber": 1, "pageSize": 5, "tradingName": "WEG"}))
    d = requests.get(url, headers=CABECALHO, timeout=30).json()
    resultados = d.get("results") or []
    assert resultados, "histórico de proventos vazio"
    for campo in ("valueCash", "lastDatePriorEx", "closingPricePriorExDate"):
        assert campo in resultados[0], f"campo {campo} sumiu"
    return f"{d['page']['totalRecords']} proventos da WEG"


def checar_b3_cotacao():
    d = requests.get("https://cotacao.b3.com.br/mds/api/v1/instrumentQuotation/WEGE3", headers=CABECALHO, timeout=30).json()
    preco = d["Trad"][0]["scty"]["SctyQtn"]["curPrc"]
    data = d["Msg"]["dtTm"][:10]
    assert preco and preco > 0, "cotação sem preço"
    assert _dias(data) <= 5, f"cotação parada desde {data}"
    return f"WEGE3 R$ {preco} em {data}"


def checar_b3_curva_di():
    for i in range(8):
        dia = date.today() - timedelta(days=i)
        if dia.weekday() >= 5:
            continue
        r = requests.get(f"https://www.b3.com.br/pesquisapregao/download?filelist=TS{dia:%y%m%d}.ex_",
                         headers=CABECALHO, timeout=60)
        if r.status_code == 200 and r.content.startswith(b"PK"):
            return f"arquivo de swaps de {dia:%d/%m/%Y} disponível"
    raise AssertionError("nenhum arquivo de swaps (curva DI) nos últimos 8 dias")


def checar_bcb():
    dados = requests.get("https://api.bcb.gov.br/dados/serie/bcdata.sgs.4389/dados/ultimos/1?formato=json", timeout=60).json()
    data = datetime.strptime(dados[-1]["data"], "%d/%m/%Y").date().isoformat()
    assert _dias(data) <= 7, f"CDI parado desde {data}"
    return f"CDI {dados[-1]['valor']}% em {data}"


def checar_focus():
    url = ("https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais"
           "?$top=1&$filter=Indicador%20eq%20'IPCA'&$orderby=Data%20desc&$format=json&$select=Data,Mediana")
    d = requests.get(url, timeout=60).json()["value"][0]
    assert _dias(d["Data"]) <= 12, f"Focus parado desde {d['Data']}"
    return f"Focus de {d['Data']}"


def checar_tesouro():
    url = ("https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/"
           "resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv")
    r = requests.get(url, timeout=60, stream=True)
    r.raise_for_status()
    cabecalho = next(r.iter_lines()).decode("latin1")
    assert "Taxa Compra Manha" in cabecalho, "colunas do arquivo do Tesouro mudaram"
    arq = DIR_DADOS_SITE / "tesouro.json"
    if arq.exists():
        base = json.loads(arq.read_text(encoding="utf-8"))["data_base"]
        assert _dias(base) <= 7, f"dados do Tesouro parados em {base}"
        return f"arquivo ok; última data {base}"
    return "arquivo ok"


def checar_yahoo():
    import yfinance as yf
    hist = yf.Ticker("WEGE3.SA").history(period="10d")
    assert not hist.empty, "Yahoo não devolveu histórico (pode estar bloqueando)"
    ultimo = hist.index[-1].date().isoformat()
    assert _dias(ultimo) <= 6, f"Yahoo parado em {ultimo}"
    return f"WEGE3 até {ultimo}"


def checar_atualizacao():
    """Resultado da própria atualização (status.json gerado por pipeline.rodar)."""
    arq = DIR_DADOS_SITE / "status.json"
    assert arq.exists(), "status.json não foi gerado"
    status = json.loads(arq.read_text(encoding="utf-8"))
    falhas = [f"{nome}: {info.get('erro', '')}" for nome, info in status["etapas"].items() if not info.get("ok")]
    assert not falhas, "etapas com erro — " + "; ".join(falhas)
    return f"todas as etapas ok ({status['atualizado_em']})"


CHECAGENS = {
    "Atualização (pipeline)": checar_atualizacao,
    "CVM — ITR/DFP": checar_cvm,
    "CVM — cadastro": checar_cvm_cadastro,
    "CVM — fatos relevantes e Formulário de Referência": checar_cvm_ipe_fre,
    "B3 — dados da empresa": checar_b3_empresa,
    "B3 — histórico de proventos": checar_b3_proventos,
    "B3 — cotação": checar_b3_cotacao,
    "B3 — curva DI (swaps)": checar_b3_curva_di,
    "Banco Central — SGS": checar_bcb,
    "Banco Central — Focus": checar_focus,
    "Tesouro Direto": checar_tesouro,
    "Yahoo Finance": checar_yahoo,
}


def main():
    resultados = {}
    for nome, funcao in CHECAGENS.items():
        try:
            resultados[nome] = {"ok": True, "detalhe": funcao()}
        except Exception as e:
            resultados[nome] = {"ok": False, "detalhe": str(e)[:300] or repr(e)}
        marca = "✅" if resultados[nome]["ok"] else "❌"
        print(f"{marca} {nome}: {resultados[nome]['detalhe']}")

    (DIR_DADOS_SITE / "saude.json").write_text(json.dumps(
        {"verificado_em": datetime.now().isoformat(timespec="seconds"), "fontes": resultados},
        ensure_ascii=False, indent=1), encoding="utf-8")

    falhas = {n: r for n, r in resultados.items() if not r["ok"]}
    if falhas:
        linhas = [f"O monitor da R.V. Mapp encontrou {len(falhas)} problema(s) em {date.today():%d/%m/%Y}:", ""]
        linhas += [f"- **{n}**: {r['detalhe']}" for n, r in falhas.items()]
        linhas += ["", "O site continua publicado com os últimos dados bons das fontes que funcionaram."]
        ARQ_ALERTA.write_text("\n".join(linhas), encoding="utf-8")
    elif ARQ_ALERTA.exists():
        ARQ_ALERTA.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
