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
from datetime import date, datetime, timedelta, timezone

import requests

from pipeline import DIR_DADOS_SITE, DIR_INTERMEDIARIO, sem_segredos

CABECALHO = {"User-Agent": "Mozilla/5.0"}
ARQ_ALERTA = DIR_INTERMEDIARIO / "alerta.md"
FUSO_BR = timezone(timedelta(hours=-3))
ARQ_OBSERVACOES = DIR_INTERMEDIARIO / "observacoes.json"  # guarda desde quando cada problema está aberto


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
            import io
            import zipfile
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                if not z.namelist():
                    continue  # ZIP do dia ainda vazio
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


def checar_tesouro_tempo_real():
    """Preços do momento do site do Tesouro Direto (não oficial), gerados por pipeline.tesouro."""
    tes = json.loads((DIR_DADOS_SITE / "tesouro.json").read_text(encoding="utf-8"))
    assert not tes.get("falha_tempo_real"), tes["falha_tempo_real"]
    tr = tes.get("tempo_real")
    if not tr:  # fora do horário: o último preço do Tesouro Direto não é mais novo que o oficial
        return "sem preço mais novo que a referência oficial"
    return f"{len(tr['titulos'])} títulos precificados em {tr['precificado_em'].replace('T', ' ')}"


def checar_yahoo():
    import yfinance as yf
    hist = yf.Ticker("WEGE3.SA").history(period="10d")
    assert not hist.empty, "Yahoo não devolveu histórico (pode estar bloqueando)"
    ultimo = hist.index[-1].date().isoformat()
    assert _dias(ultimo) <= 6, f"Yahoo parado em {ultimo}"
    return f"WEGE3 até {ultimo}"


def checar_agenda():
    """Calendários do Banco Central, IBGE e FGV (gerados por pipeline.agenda)."""
    arq = DIR_DADOS_SITE / "agenda.json"
    assert arq.exists(), "agenda.json não foi gerado"
    agenda = json.loads(arq.read_text(encoding="utf-8"))
    assert not agenda["falhas"], "fonte da agenda falhou — " + "; ".join(agenda["falhas"])
    fontes = {e["fonte"] for e in agenda["eventos"]}
    faltando = {"Banco Central", "IBGE"} - fontes
    assert not faltando, f"agenda sem eventos de {', '.join(faltando)}"
    return f"{len(agenda['eventos'])} eventos ({', '.join(sorted(fontes))})"


def checar_noticias():
    """Feeds de notícias (Banco Central, IBGE, CVM, Agência Brasil), gerados por pipeline.noticias."""
    arq = DIR_DADOS_SITE / "noticias.json"
    assert arq.exists(), "noticias.json não foi gerado"
    d = json.loads(arq.read_text(encoding="utf-8"))
    assert not d["falhas"], "fonte de notícias falhou — " + "; ".join(d["falhas"])
    assert d["itens"], "nenhuma manchete"
    assert _dias(d["itens"][0]["data"]) <= 4, f"manchete mais recente é de {d['itens'][0]['data'][:10]}"
    return f"{len(d['itens'])} manchetes; mais recente {d['itens'][0]['data'][:10]}"


# Validação das séries do Macro: (frequência, defasagem máxima em dias, faixa plausível de valores)
# Defasagem conta da data do último ponto (dia 1 do mês/trimestre/ano de referência) até hoje.
SERIES_MACRO = {
    "ipca": ("M", 75, (-3, 5)), "igpm": ("M", 75, (-6, 9)), "incc": ("M", 75, (-3, 6)),
    "nucleo_ex0": ("M", 75, (-2, 4)), "nucleo_ex2": ("M", 75, (-2, 4)), "nucleo_ex3": ("M", 75, (-2, 4)),
    "nucleo_ms": ("M", 75, (-2, 4)), "nucleo_dp": ("M", 75, (-2, 4)), "nucleo_p55": ("M", 75, (-2, 4)),
    "ibcbr": ("M", 110, (50, 250)), "ibcbr_dessaz": ("M", 110, (50, 250)),
    "pib_indice": ("T", 250, (50, 400)), "pib_indice_obs": ("T", 250, (50, 400)),
    "pib_anual": ("A", 800, (-10, 15)), "pib_nominal": ("A", 800, (1e11, 1e14)),
    "desemprego": ("M", 100, (2, 20)),
    "nfsp_primario": ("M", 110, (-10, 15)), "nfsp_nominal": ("M", 110, (-5, 25)), "nfsp_juros": ("M", 110, (0, 20)),
    "dlsp": ("M", 110, (10, 120)), "dbgg": ("M", 110, (30, 150)), "dmf_selic": ("M", 110, (0, 100)), "dmf_pre": ("M", 110, (0, 100)),
    "selic_meta": ("D", 6, (1, 30)), "cdi": ("D", 6, (1, 30)), "usd": ("D", 6, (1, 15)), "eur": ("D", 6, (1, 15)),
}
PASSO_MESES = {"M": 1, "T": 3, "A": 12}


def _url_site():
    import os
    dono, _, repo = os.environ.get("GITHUB_REPOSITORY", "fredperin/screeening-cvm").partition("/")
    return f"https://{dono}.github.io/{repo}"


def checar_macro():
    """Cada série do Macro: completa, sem buracos, em dia, com valores plausíveis e não menor que a publicada."""
    macro = json.loads((DIR_DADOS_SITE / "macro.json").read_text(encoding="utf-8"))
    S, problemas = macro["series"], []
    if macro.get("falhas"):
        problemas.append("séries mantidas na versão anterior por falha da API — " + "; ".join(macro["falhas"]))
    for chave, (freq, max_dias, (minimo, maximo)) in SERIES_MACRO.items():
        s = S.get(chave)
        if not s or not s["datas"]:
            problemas.append(f"{chave}: série ausente ou vazia")
            continue
        if _dias(s["datas"][-1]) > max_dias:
            problemas.append(f"{chave}: último dado em {s['datas'][-1]} (mais de {max_dias} dias)")
        fora = [(d, v) for d, v in zip(s["datas"], s["valores"]) if not (minimo <= v <= maximo)]
        if fora:
            problemas.append(f"{chave}: {len(fora)} valor(es) fora da faixa plausível, ex. {fora[-1][0]} = {fora[-1][1]}")
        if freq in PASSO_MESES:
            meses = [int(d[:4]) * 12 + int(d[5:7]) for d in s["datas"]]
            buracos = [s["datas"][i] for i in range(1, len(meses)) if meses[i] - meses[i - 1] != PASSO_MESES[freq]]
            if buracos:
                problemas.append(f"{chave}: {len(buracos)} buraco(s) na série, o primeiro antes de {buracos[0]}")
    for k, anos in macro.get("focus", {}).items():
        atual = anos.get(str(date.today().year))
        if not atual or _dias(atual["datas"][-1]) > 12:
            problemas.append(f"Focus {k}: sem projeção recente para {date.today().year}")

    # Comparação com a versão publicada no site (antes desta atualização)
    comparadas = 0
    try:
        publicada = requests.get(f"{_url_site()}/dados/macro.json", timeout=60).json()["series"]
        for chave, s in S.items():
            p = publicada.get(chave)
            if not p or not p["datas"]:
                continue
            comparadas += 1
            if s["datas"][-1] < p["datas"][-1] or s["datas"][0] > p["datas"][0] or (chave != "selic_meta" and len(s["datas"]) < len(p["datas"])):
                problemas.append(f"{chave}: menor que a versão publicada ({s['datas'][0]}–{s['datas'][-1]}, {len(s['datas'])} pontos;"
                                 f" publicada {p['datas'][0]}–{p['datas'][-1]}, {len(p['datas'])} pontos)")
    except Exception as e:
        comparadas = f"não comparado com o site ({str(e)[:60]})"

    assert not problemas, " | ".join(problemas)
    return f"{len(SERIES_MACRO)} séries em dia, completas e sem buracos; comparadas com o site: {comparadas}"


def checar_offshore():
    """Dados do exterior: nenhuma fonte com falha e cada série dentro da defasagem esperada."""
    off = json.loads((DIR_DADOS_SITE / "offshore.json").read_text(encoding="utf-8"))
    problemas = list(off.get("falhas", []))
    T, F, B, E, Z = (off.get(k, {}) for k in ("treasuries", "fed", "bls", "bce", "eurostat"))
    limites = [("Treasury 10 anos", T.get("historico", {}).get("10 anos"), 6), ("EFFR", F.get("effr"), 6), ("SOFR", F.get("sofr"), 6),
               ("€STR", E.get("estr"), 6), ("curva AAA do BCE", E.get("aaa_10a"), 6), ("CPI EUA", B.get("cpi_12m"), 75),
               ("desemprego EUA", B.get("desemprego"), 75), ("HICP", Z.get("hicp_12m"), 75), ("desemprego Zona do Euro", Z.get("desemprego"), 100),
               ("PIB Zona do Euro", Z.get("pib_tri"), 250), ("produção industrial Zona do Euro", Z.get("producao_12m"), 100),
               ("PCE EUA (FRED)", off.get("fred", {}).get("pce_12m"), 75), ("PIB EUA (FRED)", off.get("fred", {}).get("pib_tri_anual"), 200),
               ("confiança do consumidor EUA (FRED)", off.get("fred", {}).get("confianca"), 75)]
    for nome, s, max_dias in limites:
        if not s or not s.get("datas"):
            problemas.append(f"{nome}: série ausente")
        elif _dias(s["datas"][-1]) > max_dias:
            problemas.append(f"{nome}: último dado em {s['datas'][-1]}")
    agenda = DIR_DADOS_SITE / "agenda_offshore.json"
    if agenda.exists():
        problemas += json.loads(agenda.read_text(encoding="utf-8")).get("falhas", [])
    assert not problemas, " | ".join(problemas)
    return f"{len(limites)} séries em dia (Tesouro dos EUA, Fed, BLS, FRED, BCE, Eurostat)"


def checar_mundo():
    """Mercados (FRED), commodities (Banco Mundial), China (OCDE) e Global (FMI), gerados por pipeline.mundo."""
    arq = DIR_DADOS_SITE / "mundo.json"
    assert arq.exists(), "mundo.json não foi gerado"
    m = json.loads(arq.read_text(encoding="utf-8"))
    problemas = list(m.get("falhas", []))
    limites = [("S&P 500 (FRED)", (m.get("mercados") or {}).get("sp500"), 6), ("Brent (FRED)", (m.get("mercados") or {}).get("brent"), 10),
               ("minério de ferro (Banco Mundial)", (m.get("commodities") or {}).get("minerio"), 75),
               ("CPI China (OCDE)", (m.get("china") or {}).get("cpi_12m"), 75), ("PIB China (OCDE)", (m.get("china") or {}).get("pib_12m"), 200)]
    for nome, s, max_dias in limites:
        if not s or not s.get("datas"):
            problemas.append(f"{nome}: série ausente")
        elif _dias(s["datas"][-1]) > max_dias:
            problemas.append(f"{nome}: último dado em {s['datas'][-1]}")
    if not (m.get("global") or {}).get("indicadores"):
        problemas.append("FMI: indicadores ausentes")
    assert not problemas, " | ".join(problemas)
    return "mercados, commodities, China e Global em dia"


def checar_empresas_mundo():
    """Empresas do S&P 500 (pipeline.empresas_mundo): tabelão gerado, quase todas as empresas e cotações do último pregão."""
    arq = DIR_DADOS_SITE / "mundo_empresas.json"
    assert arq.exists(), "mundo_empresas.json não foi gerado"
    m = json.loads(arq.read_text(encoding="utf-8"))
    problemas = []
    if len(m["empresas"]) < 450:
        problemas.append(f"só {len(m['empresas'])} empresas do S&P 500 com dados")
    com_preco = sum(1 for e in m["empresas"] if e.get("preco"))
    if com_preco < len(m["empresas"]) * 0.9:
        problemas.append(f"cotação em só {com_preco} de {len(m['empresas'])} empresas (Yahoo)")
    if _dias(m["gerado_em"]) > 4:
        problemas.append(f"tabelão gerado em {m['gerado_em']}")
    assert not problemas, " | ".join(problemas)
    return f"{len(m['empresas'])} empresas; {com_preco} com cotação"


def checar_credito():
    """Estatísticas de crédito do BC (pipeline.credito): sem falhas e com o último mês dentro da defasagem normal (~30 dias)."""
    arq = DIR_DADOS_SITE / "credito.json"
    assert arq.exists(), "credito.json não foi gerado"
    c = json.loads(arq.read_text(encoding="utf-8"))
    problemas = [f"séries mantidas na versão anterior — {'; '.join(c['falhas'][:5])}"] if c.get("falhas") else []
    for k in ("saldo_total", "conc_total", "taxa_total", "inad_total", "endiv"):
        s = c["series"].get(k)
        if not s or not s["datas"]:
            problemas.append(f"{k}: série ausente")
        elif _dias(s["datas"][-1]) > (130 if k == "endiv" else 100):
            problemas.append(f"{k}: último dado em {s['datas'][-1]}")
    assert not problemas, " | ".join(problemas)
    return f"{len(c['series'])} séries; último mês {c['series']['saldo_total']['datas'][-1][:7]}"


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
    "Macro — séries completas e em dia": checar_macro,
    "Banco Central — estatísticas de crédito": checar_credito,
    "Mundo — mercados, commodities, China e Global": checar_mundo,
    "Mundo — empresas do S&P 500 (SEC)": checar_empresas_mundo,
    "Offshore — Tesouro dos EUA, Fed, BLS, BCE, Eurostat": checar_offshore,
    "Tesouro Direto (oficial)": checar_tesouro,
    "Tesouro Direto — tempo real (não oficial)": checar_tesouro_tempo_real,
    "Yahoo Finance": checar_yahoo,
    "Agenda (Banco Central, IBGE, FGV)": checar_agenda,
    "Notícias (Banco Central, IBGE, CVM, Agência Brasil)": checar_noticias,
}


def gravar_observacoes(falhas):
    """Observações do site: um item por checagem com falha; some quando a checagem volta a passar."""
    agora = datetime.now(FUSO_BR).isoformat(timespec="minutes")
    try:
        anteriores = {o["fonte"]: o for o in json.loads(ARQ_OBSERVACOES.read_text(encoding="utf-8"))["abertas"]}
    except (OSError, ValueError, KeyError):
        anteriores = {}
    abertas = [{"fonte": nome, "detalhe": r["detalhe"], "desde": anteriores.get(nome, {}).get("desde", agora)}
               for nome, r in falhas.items()]
    resolvidas = sorted(set(anteriores) - set(falhas))
    conteudo = json.dumps({"verificado_em": agora, "abertas": abertas, "resolvidas_agora": resolvidas}, ensure_ascii=False, indent=1)
    ARQ_OBSERVACOES.write_text(conteudo, encoding="utf-8")
    (DIR_DADOS_SITE / "observacoes.json").write_text(conteudo, encoding="utf-8")


def main():
    import time
    resultados = {}
    for nome, funcao in CHECAGENS.items():
        # até 3 tentativas: oscilação momentânea de uma API não deve virar alerta
        for tentativa in range(3):
            try:
                resultados[nome] = {"ok": True, "detalhe": sem_segredos(funcao())}
                break
            except Exception as e:
                resultados[nome] = {"ok": False, "detalhe": sem_segredos(str(e)[:300] or repr(e))}
                if tentativa < 2:
                    time.sleep(15)
        marca = "✅" if resultados[nome]["ok"] else "❌"
        print(f"{marca} {nome}: {resultados[nome]['detalhe']}")

    (DIR_DADOS_SITE / "saude.json").write_text(json.dumps(
        {"verificado_em": datetime.now(FUSO_BR).isoformat(timespec="seconds"), "fontes": resultados},
        ensure_ascii=False, indent=1), encoding="utf-8")

    falhas = {n: r for n, r in resultados.items() if not r["ok"]}
    gravar_observacoes(falhas)
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
