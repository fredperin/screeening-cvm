"""
Fundos imobiliários de tijolo (plano em docs/plano-fiis.md): visão geral do mercado, planilhão e página de cada fundo.

Universo: FII com cota negociada na bolsa, informe mensal recente, imóveis físicos (terrenos e imóveis prontos, em construção
ou para venda) somando pelo menos metade do ativo, imóvel pronto para renda no informe trimestral e negócio na B3 no último mês.
Fundos de papel (CRI), fundos de fundos e os que só têm participação em sociedades (SPEs) ficam de fora.

Fontes (gratuitas, sem chave):
- CVM, dados abertos — informe mensal de FII (cadastro, patrimônio, cotas, valor patrimonial da cota, cotistas, DY e rentabilidade
  do mês, composição do ativo e do passivo) e informe trimestral (imóveis: área, vacância, inadimplência, % da receita; locatários
  por setor). Cada ZIP só é baixado de novo quando a CVM o republica.
- B3 — arquivo oficial diário de cotações (COTAHIST_D): ticker de cada ISIN, último fechamento e volume negociado (liquidez).
  Cada dia é baixado uma vez e guardado só com as linhas de FII.
- Fundos.NET (B3) — lista de documentos de cada fundo (aba Documentos) e avisos estruturados "Rendimentos e Amortizações"
  (XML: data-com, valor por cota e pagamento), que são a fonte dos rendimentos. Cada aviso é lido uma vez só.
- Yahoo (não oficial, sinalizado): cotação semanal de 10 anos (gráficos) e rendimentos anteriores ao primeiro aviso lido (data ex).

Cálculos (sempre indicados no site): P/VP = preço ÷ valor patrimonial da cota do último informe mensal; DY 12m = rendimentos com data
nos últimos 12 meses ÷ preço; vacância física = área vaga ÷ área dos imóveis prontos para renda; inadimplência = média dos imóveis
ponderada pela participação de cada um na receita; liquidez = volume financeiro médio por pregão no último mês.

Saídas: site/dados/fiis.json (visão geral e planilhão), site/dados/fiis/{TICKER}.json (página do fundo),
site/downloads/fiis.xlsx (seção) e site/downloads/fiis/{TICKER}.xlsx (cada fundo).
Uso: py -m pipeline.fiis
"""

import io
import json
import statistics
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests

from pipeline import DIR_DADOS_SITE, DIR_DOWNLOADS_SITE, DIR_INTERMEDIARIO, sem_segredos

ARQ = DIR_DADOS_SITE / "fiis.json"
DIR_FUNDOS = DIR_DADOS_SITE / "fiis"
ARQ_XLSX = DIR_DOWNLOADS_SITE / "fiis.xlsx"
DIR_XLSX = DIR_DOWNLOADS_SITE / "fiis"
DIR_CACHE = DIR_INTERMEDIARIO / "fiis"
DIR_COTAHIST = DIR_CACHE / "cotahist"
ARQ_META = DIR_CACHE / "arquivos.json"
FUSO_BR = timezone(timedelta(hours=-3))
CABECALHO = {"User-Agent": "Mozilla/5.0 (R.V. Mapp; dados abertos)"}

URL_MENSAL = "https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/inf_mensal_fii_{ano}.zip"
URL_TRIMESTRAL = "https://dados.cvm.gov.br/dados/FII/DOC/INF_TRIMESTRAL/DADOS/inf_trimestral_fii_{ano}.zip"
URL_FNET = ("https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados?d=0&s={inicio}&l={qtd}"
            "&o[0][dataEntrega]=desc&cnpjFundo={cnpj}")
URL_DOC_FNET = "https://fnet.bmfbovespa.com.br/fnet/publico/exibirDocumento?id={id}"
URL_XML_FNET = "https://fnet.bmfbovespa.com.br/fnet/publico/downloadDocumento?id={id}"
DIR_AVISOS = DIR_CACHE / "avisos_rendimentos"
MESES_AVISOS = 14           # avisos estruturados de rendimentos lidos para trás (o DY 12m precisa de 12 meses)
MAX_AVISOS_EXECUCAO = 700   # primeira carga espalhada em algumas execuções (os mais recentes primeiro)
DIR_DOCS = DIR_CACHE / "documentos"
DOCS_INICIAIS = 300         # primeira carga: os 300 documentos mais recentes de cada fundo
DOCS_DIARIOS = 40           # depois, só a primeira página (os mais recentes) a cada atualização
URL_COTAHIST = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_D{ddmmaaaa}.ZIP"
INICIO_MENSAL = 2019        # histórico mensal (valor patrimonial, PL, cotistas) desde jan/2019
ANOS_TRIMESTRAL = 3         # vacância e inadimplência dos últimos 3 anos
PREGOES_LIQUIDEZ = 21       # liquidez = média do último mês de pregões
MAX_DIAS_INFORME = 150      # fundo sem informe mensal há mais tempo fica de fora (encerrado ou inadimplente com a CVM)
MIN_IMOVEIS_ATIVO = 0.5     # imóveis físicos ≥ 50% do ativo


# ---------------- downloads ----------------
def _meta():
    try:
        return json.loads(ARQ_META.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def baixar_cvm(url, nome, meta):
    """ZIP da CVM com cópia local: baixa de novo só quando a CVM o republica (Last-Modified/tamanho). None = ano não publicado."""
    DIR_CACHE.mkdir(parents=True, exist_ok=True)
    local = DIR_CACHE / nome
    try:
        cab = requests.head(url, headers=CABECALHO, timeout=60)
    except requests.RequestException:
        if local.exists():
            return local  # sem resposta: fica a cópia anterior (o monitor vigia a defasagem)
        raise
    if cab.status_code == 404:
        return None
    cab.raise_for_status()
    assinatura = f"{cab.headers.get('Last-Modified')}|{cab.headers.get('Content-Length')}"
    if local.exists() and meta.get(nome) == assinatura:
        return local
    print(f"📥 {nome}: baixando (novo ou republicado pela CVM)")
    r = requests.get(url, headers=CABECALHO, timeout=300)
    r.raise_for_status()
    zipfile.ZipFile(io.BytesIO(r.content)).testzip()  # arquivo íntegro antes de substituir a cópia
    local.write_bytes(r.content)
    meta[nome] = assinatura
    return local


def _ler(zip_path, prefixo, ano):
    with zipfile.ZipFile(zip_path) as z:
        nome = f"{prefixo}_{ano}.csv"
        if nome not in z.namelist():
            return pd.DataFrame()
        return pd.read_csv(io.BytesIO(z.read(nome)), sep=";", encoding="latin1", dtype=str)


def _ultima_versao(d, linhas_multiplas=False):
    """Fica com a última Versao de cada (fundo, data). Arquivos com várias linhas por informe (imóveis, locatários) mantêm
    todas as linhas da última versão."""
    if d.empty:
        return d
    d = d.copy()
    d["Versao"] = pd.to_numeric(d["Versao"], errors="coerce").fillna(0)
    chave = ["CNPJ_Fundo_Classe", "Data_Referencia"]
    if linhas_multiplas:
        return d[d["Versao"] == d.groupby(chave)["Versao"].transform("max")]
    return d.sort_values(chave + ["Versao"]).drop_duplicates(chave, keep="last")


def informes_cvm(meta):
    hoje = date.today()
    mensal = {"geral": [], "complemento": [], "ativo_passivo": []}
    for ano in range(INICIO_MENSAL, hoje.year + 1):
        z = baixar_cvm(URL_MENSAL.format(ano=ano), f"inf_mensal_fii_{ano}.zip", meta)
        if z is None:
            continue
        for k in mensal:
            mensal[k].append(_ler(z, f"inf_mensal_fii_{k}", ano))
    mensal = {k: _ultima_versao(pd.concat(v, ignore_index=True)) for k, v in mensal.items()}
    tri = {"geral": [], "imovel": [], "imovel_renda_acabado_inquilino": []}
    for ano in range(hoje.year - ANOS_TRIMESTRAL, hoje.year + 1):
        z = baixar_cvm(URL_TRIMESTRAL.format(ano=ano), f"inf_trimestral_fii_{ano}.zip", meta)
        if z is None:
            continue
        for k in tri:
            tri[k].append(_ler(z, f"inf_trimestral_fii_{k}", ano))
    tri = {k: _ultima_versao(pd.concat(v, ignore_index=True), linhas_multiplas=k != "geral") for k, v in tri.items()}
    return mensal, tri


# ---------------- B3: arquivo diário de cotações (COTAHIST) ----------------
def _ler_cotahist(conteudo):
    """Linhas de FII (CODBDI 12) do mercado à vista: ticker, ISIN, fechamento e volume do dia."""
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        texto = z.read(z.namelist()[0]).decode("latin1")
    linhas = []
    for l in texto.splitlines():
        if l[:2] != "01" or l[10:12] != "12" or l[24:27] != "010":
            continue
        linhas.append({"ticker": l[12:24].strip(), "isin": l[230:242], "fechamento": int(l[108:121]) / 100,
                       "negocios": int(l[147:152]), "volume": int(l[170:188]) / 100})
    return linhas


def cotahist(meta):
    """Últimos PREGOES_LIQUIDEZ pregões: um arquivo por dia, baixado uma vez e guardado só com os FIIs.
    Dia sem arquivo há mais de 4 dias = sem pregão (feriado), não é pedido de novo."""
    DIR_COTAHIST.mkdir(parents=True, exist_ok=True)
    sem_pregao = set(meta.get("sem_pregao", []))
    hoje = date.today()
    dias, falhas, d = [], [], hoje
    while len(dias) < PREGOES_LIQUIDEZ and (hoje - d).days <= 50:
        if d.weekday() < 5 and d.isoformat() not in sem_pregao:
            arq = DIR_COTAHIST / f"{d.isoformat()}.json"
            if not arq.exists():
                try:
                    r = requests.get(URL_COTAHIST.format(ddmmaaaa=d.strftime("%d%m%Y")), headers=CABECALHO, timeout=60)
                    if r.status_code == 404 or (r.ok and not r.content.startswith(b"PK")):
                        if (hoje - d).days > 4:
                            sem_pregao.add(d.isoformat())
                    else:
                        r.raise_for_status()
                        arq.write_text(json.dumps(_ler_cotahist(r.content)), encoding="utf-8")
                except (requests.RequestException, zipfile.BadZipFile, ValueError) as e:
                    falhas.append(f"COTAHIST {d.isoformat()}: {e!r}"[:200])
            if arq.exists():
                dias.append((d.isoformat(), json.loads(arq.read_text(encoding="utf-8"))))
        d -= timedelta(days=1)
    meta["sem_pregao"] = sorted(x for x in sem_pregao if (hoje - date.fromisoformat(x)).days <= 60)
    for velho in DIR_COTAHIST.glob("*.json"):  # o cache guarda só ~2 meses
        if (hoje - date.fromisoformat(velho.stem)).days > 70:
            velho.unlink()
    return sorted(dias), falhas


def negocios_por_ticker(dias):
    """ticker -> {isin, preco, data_preco, liquidez (volume médio por pregão no período, dias sem negócio contam 0)}."""
    if not dias:
        return {}
    saida = {}
    for data, linhas in dias:
        for x in linhas:
            s = saida.setdefault(x["ticker"], {"isin": x["isin"], "volume": 0.0, "negocios": 0})
            s["volume"] += x["volume"]
            s["negocios"] += x["negocios"]
            s["preco"], s["data_preco"] = x["fechamento"], data  # dias em ordem: fica o último fechamento
    for s in saida.values():
        s["liquidez"] = s.pop("volume") / len(dias)
    return saida


# ---------------- Fundos.NET: documentos e fatos relevantes ----------------
def _data_fnet(s):
    """'30/10/2026 17:31' -> '2026-10-30 17:31'; '10/2026' -> '2026-10'."""
    s = (s or "").strip()
    try:
        if len(s) >= 10 and s[2] == "/" and s[5] == "/":
            return f"{s[6:10]}-{s[3:5]}-{s[:2]}{s[10:]}"
        if len(s) == 7 and s[2] == "/":
            return f"{s[3:]}-{s[:2]}"
    except IndexError:
        pass
    return s or None


def documentos_fnet(cnpj):
    """Lista de documentos do fundo no Fundos.NET, com cópia local: a primeira vez traz os DOCS_INICIAIS mais recentes; depois,
    só a primeira página, juntada à cópia pelo id do documento. Falha -> fica a cópia anterior (e o erro volta para o chamador)."""
    DIR_DOCS.mkdir(parents=True, exist_ok=True)
    arq = DIR_DOCS / f"{cnpj.replace('.', '').replace('/', '').replace('-', '')}.json"
    try:
        guardado = json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        guardado = []
    alvo = DOCS_DIARIOS if guardado else DOCS_INICIAIS
    novos = []
    for inicio in range(0, alvo, 100):
        r = requests.get(URL_FNET.format(inicio=inicio, qtd=min(100, alvo - inicio), cnpj=arq.stem),
                         headers={**CABECALHO, "X-Requested-With": "XMLHttpRequest"}, timeout=60)
        r.raise_for_status()
        pagina = r.json().get("data") or []
        novos += [{"id": x["id"], "data": _data_fnet(x.get("dataEntrega")), "referencia": _data_fnet(x.get("dataReferencia")),
                   "categoria": (x.get("categoriaDocumento") or "").strip(), "tipo": (x.get("tipoDocumento") or "").strip(),
                   "especie": (x.get("especieDocumento") or "").strip(), "assunto": (x.get("assuntos") or "").strip() if isinstance(x.get("assuntos"), str) else "",
                   "status": (x.get("descricaoStatus") or "").strip()} for x in pagina]
        if len(pagina) < 100:
            break
    por_id = {d["id"]: d for d in guardado} | {d["id"]: d for d in novos}
    docs = sorted(por_id.values(), key=lambda d: (d["data"] or "", d["id"]), reverse=True)
    arq.write_text(json.dumps(docs, ensure_ascii=False), encoding="utf-8")
    return docs


def _documentos_com_cache(cnpj):
    try:
        return documentos_fnet(cnpj), None
    except Exception as e:  # noqa: BLE001
        arq = DIR_DOCS / f"{cnpj.replace('.', '').replace('/', '').replace('-', '')}.json"
        try:
            docs = json.loads(arq.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            docs = []
        return docs, f"Fundos.NET {cnpj}: {e!r}"[:200]


# ---------------- Fundos.NET: rendimentos oficiais (avisos estruturados) ----------------
def _aviso_rendimento(d):
    return d["categoria"].startswith("Aviso aos Cotistas - Estruturado") and "Rendimento" in d["tipo"] and d["status"].startswith("Ativo")


def ler_aviso(id_doc):
    """XML do aviso estruturado 'Rendimentos e Amortizações': lista de {ticker, tipo, data_com, valor, pagamento, referencia}.
    Cada aviso é baixado uma vez só (documento entregue não muda; correção vem em documento novo)."""
    import xml.etree.ElementTree as ET
    DIR_AVISOS.mkdir(parents=True, exist_ok=True)
    arq = DIR_AVISOS / f"{id_doc}.json"
    if arq.exists():
        return json.loads(arq.read_text(encoding="utf-8"))
    r = requests.get(URL_XML_FNET.format(id=id_doc), headers=CABECALHO, timeout=60)
    r.raise_for_status()
    raiz = ET.fromstring(r.content)
    saida = []
    for prov in raiz.iter("Provento"):
        ticker = (prov.findtext("CodNegociacao") or "").strip().upper()
        for no in prov:
            if no.tag not in ("Rendimento", "Amortizacao"):
                continue
            valor = (no.findtext("ValorProvento") or "").strip().replace(",", ".")
            try:
                valor = float(valor)
            except ValueError:
                continue
            saida.append({"ticker": ticker, "tipo": "rendimento" if no.tag == "Rendimento" else "amortizacao",
                          "data_com": (no.findtext("DataBase") or "").strip()[:10] or None, "valor": valor,
                          "pagamento": (no.findtext("DataPagamento") or "").strip()[:10] or None,
                          "referencia": (no.findtext("PeriodoReferencia") or "").strip() or None})
    arq.write_text(json.dumps(saida, ensure_ascii=False), encoding="utf-8")
    return saida


def rendimentos_oficiais(universo, documentos, falhas):
    """ticker -> {"rendimentos": [[data-com, R$/cota, pagamento, id do aviso]], "amortizacoes": [...], "desde": data do aviso mais
    antigo lido}. Só avisos ativos (o reenviado substitui o anterior, que fica inativo)."""
    corte = (date.today() - timedelta(days=MESES_AVISOS * 31)).isoformat()
    pendentes = []
    for cnpj, ticker in universo:
        for d in documentos.get(cnpj) or []:
            if _aviso_rendimento(d) and (d["data"] or "") >= corte and not (DIR_AVISOS / f"{d['id']}.json").exists():
                pendentes.append(d)
    pendentes.sort(key=lambda d: d["data"] or "", reverse=True)
    if len(pendentes) > MAX_AVISOS_EXECUCAO:
        print(f"Avisos de rendimentos: {len(pendentes)} a ler; {MAX_AVISOS_EXECUCAO} nesta execução, o resto nas próximas")
    erros = 0
    for d in pendentes[:MAX_AVISOS_EXECUCAO]:
        try:
            ler_aviso(d["id"])
        except Exception as e:  # noqa: BLE001
            erros += 1
            if erros <= 3:
                falhas.append(sem_segredos(f"aviso de rendimentos {d['id']}: {e!r}")[:200])
    saida = {}
    for cnpj, ticker in universo:
        avisos = [d for d in documentos.get(cnpj) or [] if _aviso_rendimento(d) and (d["data"] or "") >= corte
                  and (DIR_AVISOS / f"{d['id']}.json").exists()]
        rend, amort = {}, {}
        for d in sorted(avisos, key=lambda d: d["data"] or ""):  # o aviso mais novo para a mesma data-com prevalece
            for x in json.loads((DIR_AVISOS / f"{d['id']}.json").read_text(encoding="utf-8")):
                if x["ticker"] != ticker or not x["data_com"]:
                    continue
                (rend if x["tipo"] == "rendimento" else amort)[x["data_com"]] = [x["data_com"], x["valor"], x["pagamento"], d["id"]]
        if rend or amort:
            saida[ticker] = {"rendimentos": [rend[k] for k in sorted(rend)], "amortizacoes": [amort[k] for k in sorted(amort)],
                             "desde": min(d["data"][:10] for d in avisos)}
    return saida


# ---------------- Yahoo (não oficial): cotação semanal e rendimentos ----------------
def yahoo(ticker):
    """(cotacao semanal {datas, fechamento}, rendimentos [[data ex, R$/cota], ...]). Usa o cache incremental das ações."""
    from pipeline.mercado import DIR_YAHOO, historico_yahoo
    _, cotacao = historico_yahoo(ticker)
    try:
        guardado = json.loads((DIR_YAHOO / f"{ticker}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        guardado = {}
    return cotacao or guardado.get("cotacao") or {}, guardado.get("proventos") or []


# ---------------- montagem ----------------
def _num(s):
    return pd.to_numeric(s, errors="coerce")


def _r(v, casas=4):
    return None if v is None or pd.isna(v) else round(float(v), casas)


def _lista(serie, casas=4):
    return [_r(v, casas) for v in serie]


def _texto(v):
    return None if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() in ("", "-", "nan") else str(v).strip()


ATIVO_ITENS = [("Imóveis prontos para renda", ["Imoveis_Renda_Acabados"]), ("Imóveis em construção para renda", ["Imoveis_Renda_Construcao"]),
               ("Imóveis para venda", ["Imoveis_Venda_Acabados", "Imoveis_Venda_Construcao"]), ("Terrenos", ["Terrenos"]),
               ("Outros direitos reais", ["Outros_Direitos_Reais"]),
               ("Participação em sociedades (SPEs)", ["Acoes_Sociedades_Atividades_FII", "Cotas_Sociedades_Atividades_FII"]),
               ("Cotas de outros FIIs", ["FII"]), ("CRI / CRA", ["CRI", "CRI_CRA"]), ("LCI / LCA", ["LCI", "LCI_LCA"]),
               ("Caixa e renda fixa", ["Total_Necessidades_Liquidez"]),
               ("Aluguéis e vendas a receber", ["Contas_Receber_Aluguel", "Contas_Receber_Venda_Imoveis", "Outros_Valores_Receber"])]
PASSIVO_ITENS = [("Obrigações por aquisição de imóveis", ["Obrigacoes_Aquisicao_Imoveis"]),
                 ("Obrigações de securitização de recebíveis", ["Obrigacoes_Securitizacao_Recebiveis"]),
                 ("Rendimentos a distribuir", ["Rendimentos_Distribuir"]),
                 ("Adiantamentos (aluguéis e vendas)", ["Adiantamento_Alugueis", "Adiantamento_Venda_Imoveis"]),
                 ("Taxas a pagar (administração e performance)", ["Taxa_Administracao_Pagar", "Taxa_Performance_Pagar"]),
                 ("Provisões para contingências", ["Provisoes_Contigencias"]), ("Derivativos", ["Instrumentos_Financeiros_Derivativos"]),
                 ("Outros valores a pagar", ["Outros_Valores_Pagar"])]


def composicao(linha):
    v = lambda cols: float(sum(_num(pd.Series([linha.get(c)])).fillna(0).iloc[0] for c in cols))  # noqa: E731
    return {"data": linha["Data_Referencia"], "ativo": [[n, v(c)] for n, c in ATIVO_ITENS],
            "passivo": [[n, v(c)] for n, c in PASSIVO_ITENS], "total_passivo": v(["Total_Passivo"])}


def trimestral_imoveis(im):
    """Por data do informe trimestral: nº de imóveis prontos para renda, área, vacância física e inadimplência ponderada."""
    saida = []
    for data, x in im.groupby("Data_Referencia"):
        area = x["Area"].where(x["Area"] > 0)
        rec = x["Percentual_Receitas_FII"].where(x["Percentual_Receitas_FII"] > 0)
        vac = (area * x["Percentual_Vacancia"]).sum() / area.sum() * 100 if area.sum() > 0 else None
        ina = (rec * x["Percentual_Inadimplencia"]).sum() / rec.sum() * 100 if rec.sum() > 0 else None
        saida.append({"data": data, "imoveis": int(len(x)), "area": _r(area.sum(), 0), "vacancia_fisica": _r(vac, 2),
                      "inadimplencia": _r(ina, 2)})
    return saida


def _mediana(v):
    v = [x for x in v if x is not None]
    return round(statistics.median(v), 4) if v else None


def _media(v):
    v = [x for x in v if x is not None]
    return round(sum(v) / len(v), 4) if v else None


def ntnb_5_anos():
    """Taxa real do Tesouro IPCA+ (NTN-B) mais perto de 5 anos, da curva oficial do Tesouro já usada em Juros."""
    arq = DIR_DADOS_SITE / "tesouro.json"
    if not arq.exists():
        return None
    t = json.loads(arq.read_text(encoding="utf-8"))
    curva = (t.get("curvas") or {}).get("hoje") or {}
    pontos = [p for p in curva.get("ipca") or [] if p.get("taxa") is not None]
    if not pontos:
        return None
    p = min(pontos, key=lambda p: abs(p["anos"] - 5))
    return {"taxa": p["taxa"], "vencimento": p["vencimento"], "titulo": p.get("titulo"), "data": curva.get("data")}


def gerar():
    meta = _meta()
    falhas = []
    mensal, tri = informes_cvm(meta)
    dias, f_cot = cotahist(meta)
    falhas += f_cot
    negocios = negocios_por_ticker(dias)
    anterior = json.loads(ARQ.read_text(encoding="utf-8")) if ARQ.exists() else {}
    if not negocios:
        falhas.append("COTAHIST da B3 indisponível: tickers do universo anterior e preços da Yahoo")

    g, comp, ap = mensal["geral"], mensal["complemento"], mensal["ativo_passivo"]
    # cadastro: último valor preenchido de cada campo (o mês mais recente pode vir com campos vazios)
    g = g.sort_values(["CNPJ_Fundo_Classe", "Data_Referencia"])
    cad = g.groupby("CNPJ_Fundo_Classe").agg(lambda s: s.dropna().iloc[-1] if s.notna().any() else None)
    mandato_tri = tri["geral"].sort_values("Data_Referencia").dropna(subset=["Mandato"]).groupby("CNPJ_Fundo_Classe")["Mandato"].last() \
        if not tri["geral"].empty else pd.Series(dtype=str)
    ap_ult = ap.sort_values("Data_Referencia").groupby("CNPJ_Fundo_Classe").last()
    comp_ult = comp.sort_values("Data_Referencia").groupby("CNPJ_Fundo_Classe").last()

    im = tri["imovel"]
    im = im[im["Classe"].str.contains("renda acabados", case=False, na=False)].copy()
    for k in ("Area", "Percentual_Vacancia", "Percentual_Inadimplencia", "Percentual_Receitas_FII"):
        im[k] = _num(im[k])
    com_imovel_pronto = set(im["CNPJ_Fundo_Classe"])

    # ---------------- universo de tijolo ----------------
    limite_informe = (date.today() - timedelta(days=MAX_DIAS_INFORME)).isoformat()
    tickers_anteriores = {f["cnpj"]: f["ticker"] for f in anterior.get("fundos", [])}
    por_isin = {}
    for t, s in negocios.items():
        if s["negocios"] > 0 and (s["isin"] not in por_isin or s["liquidez"] > negocios[por_isin[s["isin"]]]["liquidez"]):
            por_isin[s["isin"]] = t
    universo, fora = [], {"sem_bolsa": 0, "informe_antigo": 0, "pouco_imovel": 0, "sem_imovel_pronto": 0, "sem_negocio": 0}
    for cnpj, c in cad.iterrows():
        if c.get("Mercado_Negociacao_Bolsa") != "S":
            fora["sem_bolsa"] += 1
            continue
        if cnpj not in comp_ult.index or comp_ult.loc[cnpj, "Data_Referencia"] < limite_informe:
            fora["informe_antigo"] += 1
            continue
        ativo = _num(pd.Series([comp_ult.loc[cnpj, "Valor_Ativo"]])).iloc[0]
        imoveis = _num(pd.Series([ap_ult.loc[cnpj, "Direitos_Bens_Imoveis"]])).iloc[0] if cnpj in ap_ult.index else None
        if not (ativo and ativo > 0 and imoveis and imoveis / ativo >= MIN_IMOVEIS_ATIVO):
            fora["pouco_imovel"] += 1
            continue
        if cnpj not in com_imovel_pronto:
            fora["sem_imovel_pronto"] += 1
            continue
        ticker = por_isin.get(c.get("Codigo_ISIN")) if negocios else tickers_anteriores.get(cnpj)
        if not ticker:
            fora["sem_negocio"] += 1
            continue
        universo.append((cnpj, ticker))
    print(f"FIIs de tijolo: {len(universo)} fundos; fora: {fora}")

    with ThreadPoolExecutor(max_workers=4) as ex:
        mercado_yahoo = dict(zip([t for _, t in universo], ex.map(lambda ct: yahoo(ct[1]), universo)))
    documentos = {}
    for cnpj, _ in universo:  # em série: o Fundos.NET é consultado no ritmo de pipeline/rede.py
        documentos[cnpj], erro = _documentos_com_cache(cnpj)
        if erro:
            falhas.append(sem_segredos(erro))
    oficiais = rendimentos_oficiais(universo, documentos, falhas)

    # ---------------- cada fundo ----------------
    DIR_FUNDOS.mkdir(parents=True, exist_ok=True)
    hoje_iso = date.today().isoformat()
    inq = tri["imovel_renda_acabado_inquilino"]
    fundos, gerados = [], set()
    comp = comp.sort_values("Data_Referencia")
    comp_por = dict(tuple(comp.groupby("CNPJ_Fundo_Classe")))
    im_por = dict(tuple(im.groupby("CNPJ_Fundo_Classe")))
    inq_por = dict(tuple(inq.groupby("CNPJ_Fundo_Classe"))) if not inq.empty else {}
    for cnpj, ticker in universo:
        try:
            fundo, linha = montar_fundo(cnpj, ticker, cad.loc[cnpj], mandato_tri.get(cnpj), comp_por[cnpj], ap_ult.loc[cnpj],
                                        im_por[cnpj], inq_por.get(cnpj), negocios.get(ticker), mercado_yahoo.get(ticker) or ({}, []), oficiais.get(ticker), hoje_iso)
        except Exception as e:  # noqa: BLE001 — um fundo com problema não derruba os outros
            falhas.append(sem_segredos(f"{ticker}: {e!r}")[:300])
            continue
        fundo["documentos"] = documentos.get(cnpj) or []
        (DIR_FUNDOS / f"{ticker}.json").write_text(json.dumps(fundo, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
                                                   encoding="utf-8")
        exportar_fundo(fundo)
        fundos.append(linha)
        gerados.add(ticker)
    for velho in DIR_FUNDOS.glob("*.json"):  # fundo que saiu do universo (encerrado, virou papel, deixou de negociar)
        if velho.stem not in gerados:
            velho.unlink()
            (DIR_XLSX / f"{velho.stem}.xlsx").unlink(missing_ok=True)

    fundos.sort(key=lambda f: -(f["pl"] or 0))
    segmentos = {}
    for f in fundos:
        segmentos.setdefault(f["segmento"] or "Não informado", []).append(f)
    por_segmento = [{"segmento": s, "fundos": len(fs), "pl": sum(f["pl"] or 0 for f in fs),
                     **{f"mediana_{k}": _mediana([f[k] for f in fs if not (k == "vacancia" and f["aviso_vacancia"])])
                        for k in ("pvp", "dy12", "vacancia", "inadimplencia")}}
                    for s, fs in sorted(segmentos.items(), key=lambda x: -sum(f["pl"] or 0 for f in x[1]))]
    ntnb = ntnb_5_anos()
    dy_med = _mediana([f["dy12"] for f in fundos])
    saida = {
        "gerado_em": datetime.now(FUSO_BR).isoformat(timespec="minutes"),
        "pregoes": [dias[0][0], dias[-1][0]] if dias else None,
        "mercado": {"fundos": len(fundos), "pl": sum(f["pl"] or 0 for f in fundos),
                    "valor_mercado": sum(f["valor_mercado"] or 0 for f in fundos),
                    "cotistas": sum(f["cotistas"] or 0 for f in fundos), "liquidez": sum(f["liquidez"] or 0 for f in fundos),
                    "mediana_pvp": _mediana([f["pvp"] for f in fundos]), "mediana_dy12": dy_med,
                    "mediana_vacancia": _mediana([f["vacancia"] for f in fundos if not f["aviso_vacancia"]]),
                    "media_ponderada_pvp": (sum(f["valor_mercado"] or 0 for f in fundos if f["pvp"]) /
                                            sum(f["pl"] or 0 for f in fundos if f["pvp"])) if any(f["pvp"] for f in fundos) else None},
        "ntnb": ntnb, "spread_dy_ntnb": round(dy_med - ntnb["taxa"], 2) if dy_med is not None and ntnb else None,
        "segmentos": por_segmento, "fundos": fundos, "fora_do_universo": fora, "falhas": falhas,
        "fontes": {"cvm": "CVM — informes mensal e trimestral de FII (dados abertos)",
                   "b3": "B3 — arquivo diário de cotações (COTAHIST)", "fnet": "Fundos.NET (B3) — documentos entregues pela administradora", "yahoo": "Yahoo Finance (cotação semanal e rendimentos, não oficial)"},
    }
    ARQ_META.parent.mkdir(parents=True, exist_ok=True)
    ARQ_META.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    ARQ.write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    exportar_secao(saida)
    print(f"✅ fiis: {len(fundos)} fundos de tijolo; {len(falhas)} falha(s)")
    for f in falhas[:20]:
        print("   ⚠️", f)
    return falhas


def _data_com_pela_ex(data_ex):
    """A Yahoo registra a data ex (primeiro pregão sem direito); a data-com é o dia útil anterior (feriados não descontados)."""
    d = date.fromisoformat(data_ex[:10]) - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


def juntar_rendimentos(oficial, yahoo_prov):
    """Rendimentos por cota: os avisos oficiais do Fundos.NET (data-com) e, antes do primeiro aviso lido, a Yahoo (não oficial;
    data-com = dia útil anterior à data ex). Cada item: [data-com, R$/cota, fonte, pagamento]."""
    yahoo_prov = [[_data_com_pela_ex(d), v] for d, v in yahoo_prov]
    if not oficial or not oficial["rendimentos"]:
        return [[d, v, "yahoo", None] for d, v in yahoo_prov]
    inicio = oficial["rendimentos"][0][0]
    antes = [[d, v, "yahoo", None] for d, v in yahoo_prov if d < inicio]
    return antes + [[d, v, "fnet", pg] for d, v, pg, _ in oficial["rendimentos"]]


def montar_fundo(cnpj, ticker, c, mandato_tri, cm, a, im, inq, neg, yh, oficial, hoje_iso):
    cotacao_y, prov_yahoo = yh
    rendimentos = juntar_rendimentos(oficial, prov_yahoo)
    cm = cm[cm["Data_Referencia"] >= f"{INICIO_MENSAL}-01-01"]
    n = lambda k: _num(cm[k])  # noqa: E731
    mensal = {"datas": cm["Data_Referencia"].tolist(), "pl": _lista(n("Patrimonio_Liquido"), 0), "ativo": _lista(n("Valor_Ativo"), 0),
              "cotas": _lista(n("Cotas_Emitidas"), 0), "vp_cota": _lista(n("Valor_Patrimonial_Cotas"), 4),
              "cotistas": _lista(n("Total_Numero_Cotistas"), 0), "dy_mes": _lista(n("Percentual_Dividend_Yield_Mes") * 100, 3),
              "rent_efetiva": _lista(n("Percentual_Rentabilidade_Efetiva_Mes") * 100, 3),
              "rent_patrimonial": _lista(n("Percentual_Rentabilidade_Patrimonial_Mes") * 100, 3),
              "taxa_adm": _lista(n("Percentual_Despesas_Taxa_Administracao") * 100, 3),
              "amortizacao": _lista(n("Percentual_Amortizacao_Cotas_Mes") * 100, 3)}
    u = len(mensal["datas"]) - 1
    tri = trimestral_imoveis(im)
    ult_data = im["Data_Referencia"].max()
    ult = im[im["Data_Referencia"] == ult_data].sort_values("Percentual_Receitas_FII", ascending=False)
    imoveis = [{"nome": _texto(r.Nome_Imovel), "endereco": _texto(r.Endereco), "area": _r(r.Area, 2),
                "vacancia": _r(r.Percentual_Vacancia * 100, 2), "inadimplencia": _r(r.Percentual_Inadimplencia * 100, 2),
                "receita": _r(r.Percentual_Receitas_FII * 100, 2)} for r in ult.itertuples()]
    setores = []
    if inq is not None and not inq.empty:
        i = inq[inq["Data_Referencia"] == inq["Data_Referencia"].max()]
        s = (_num(i["Percentual_Receitas_FII"]).groupby(i["Setor_Atuacao"].fillna("Não informado").str.strip()).sum() * 100)
        setores = [[k, _r(v, 2)] for k, v in s.sort_values(ascending=False).items() if v > 0]
        setores_data = i["Data_Referencia"].max()
    else:
        setores_data = None

    # preço oficial (COTAHIST) ou, sem ele, o último fechamento semanal da Yahoo
    if neg:
        preco, data_preco, fonte_preco = neg["preco"], neg["data_preco"], "B3 (COTAHIST)"
    elif cotacao_y.get("fechamento"):
        preco, data_preco, fonte_preco = cotacao_y["fechamento"][-1], cotacao_y["datas"][-1], "Yahoo (não oficial)"
    else:
        preco = data_preco = fonte_preco = None
    vp = mensal["vp_cota"][u] if u >= 0 else None
    # 12 meses do calendário até o mês da cotação: data-com de out/2026 a nov/2025 para cotação de out/2026
    ref = date.fromisoformat(data_preco or hoje_iso)
    corte = f"{ref.year - 1}-{ref.month:02d}-99"
    janela = [r for r in rendimentos if corte < r[0] <= (data_preco or hoje_iso)]
    r12 = sum(r[1] for r in janela) if rendimentos else None
    fontes_janela = {r[2] for r in janela}
    fonte_dy = {frozenset({"fnet"}): "Fundos.NET", frozenset({"yahoo"}): "Yahoo"}.get(frozenset(fontes_janela),
                                                                                       "Fundos.NET e Yahoo" if janela else None)
    ult_rend = rendimentos[-1] if rendimentos else None
    t = tri[-1] if tri else {}
    avisos = checar_fundo(imoveis, mensal)
    cotas = mensal["cotas"][u] if u >= 0 else None
    cadastro = {"nome": _texto(c.get("Nome_Fundo_Classe")), "ticker": ticker, "cnpj": cnpj, "isin": _texto(c.get("Codigo_ISIN")),
                "administrador": _texto(c.get("Nome_Administrador")), "cnpj_administrador": _texto(c.get("CNPJ_Administrador")),
                "segmento": _texto(c.get("Segmento_Atuacao")), "mandato": _texto(mandato_tri) or _texto(c.get("Mandato")),
                "gestao": _texto(c.get("Tipo_Gestao")), "publico": _texto(c.get("Publico_Alvo")),
                "inicio": _texto(c.get("Data_Funcionamento")), "prazo": _texto(c.get("Prazo_Duracao")),
                "exclusivo": _texto(c.get("Fundo_Exclusivo")), "site": _texto(c.get("Site")), "email": _texto(c.get("Email"))}
    fundo = {"gerado_em": hoje_iso, "cadastro": cadastro, "mensal": mensal, "composicao": composicao(a), "trimestral": tri,
             "imoveis": imoveis, "imoveis_data": ult_data, "setores_inquilinos": setores, "setores_data": setores_data,
             "preco": {"valor": preco, "data": data_preco, "fonte": fonte_preco,
                       "liquidez": _r(neg["liquidez"], 0) if neg else None, "negocios": neg["negocios"] if neg else None},
             "cotacao": {"datas": cotacao_y.get("datas") or [], "fechamento": cotacao_y.get("fechamento") or []},
             "rendimentos": rendimentos, "amortizacoes": (oficial or {}).get("amortizacoes") or [], "fonte_dy": fonte_dy,
             "avisos": avisos}
    linha = {"ticker": ticker, "cnpj": cnpj, "nome": cadastro["nome"], "segmento": cadastro["segmento"], "administrador": cadastro["administrador"],
             "gestao": cadastro["gestao"], "mandato": cadastro["mandato"], "preco": preco, "data_preco": data_preco, "fonte_preco": fonte_preco,
             "vp_cota": vp, "pvp": _r(preco / vp, 4) if preco and vp else None,
             "dy12": _r(r12 / preco * 100, 2) if r12 is not None and preco else None,
             "ult_rend": ult_rend[1] if ult_rend else None, "ult_rend_data": ult_rend[0] if ult_rend else None,
             "ult_rend_pagamento": ult_rend[3] if ult_rend else None, "fonte_dy": fonte_dy,
             "pl": mensal["pl"][u] if u >= 0 else None, "valor_mercado": _r(preco * cotas, 0) if preco and cotas else None,
             "cotistas": mensal["cotistas"][u] if u >= 0 else None, "liquidez": _r(neg["liquidez"], 0) if neg else None,
             "vacancia": t.get("vacancia_fisica"), "inadimplencia": t.get("inadimplencia"), "imoveis": t.get("imoveis"), "area": t.get("area"),
             "mes_ref": mensal["datas"][u] if u >= 0 else None, "tri_ref": t.get("data"),
             "aviso_vacancia": any(a["tipo"] == "vacancia_invertida" for a in avisos), "avisos": len(avisos)}
    fundo["resumo"] = linha
    return fundo, linha


def checar_fundo(imoveis, mensal):
    """Inconsistências no que a administradora informou à CVM. O número continua igual ao da fonte; o site mostra o aviso
    e a vacância marcada fica fora das medianas."""
    avisos = []
    com_receita = [i for i in imoveis if (i["receita"] or 0) > 0 and i["vacancia"] is not None]
    if com_receita and all(i["vacancia"] >= 80 for i in com_receita):
        avisos.append({"tipo": "vacancia_invertida", "texto": "Todos os imóveis que geram receita aparecem com vacância de 80% ou mais: "
                       "a administradora parece ter informado a taxa de ocupação no campo de vacância do informe trimestral."})
    if any((i["vacancia"] or 0) > 100 or (i["inadimplencia"] or 0) > 100 for i in imoveis):
        avisos.append({"tipo": "percentual_acima_100", "texto": "Há imóvel com vacância ou inadimplência acima de 100% no informe trimestral."})
    soma = sum(i["receita"] or 0 for i in imoveis)
    if imoveis and soma > 101:
        avisos.append({"tipo": "receita_acima_100", "texto": f"A participação dos imóveis na receita soma {soma:.1f}% no informe trimestral."})
    pl, cotas = mensal["pl"], mensal["cotas"]
    for k in range(1, len(pl)):
        if pl[k] and pl[k - 1] and cotas[k] and cotas[k - 1] and cotas[k] == cotas[k - 1] and abs(pl[k] / pl[k - 1] - 1) > 0.3:
            avisos.append({"tipo": "salto_pl", "texto": f"Patrimônio líquido variou {(pl[k] / pl[k - 1] - 1) * 100:+.0f}% em "
                           f"{mensal['datas'][k][:7]} sem mudança no número de cotas (informe mensal): pode ser reavaliação dos imóveis "
                           "(laudo), venda de imóvel ou erro no informe."})
    return avisos


# ---------------- Excel ----------------
def exportar_fundo(f):
    DIR_XLSX.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame([f["cadastro"]]).T.rename(columns={0: "valor"}).to_excel(w, sheet_name="Cadastro")
        pd.DataFrame(f["mensal"]).rename(columns={
            "datas": "data", "pl": "patrimonio_liquido", "vp_cota": "valor_patrimonial_cota", "dy_mes": "dy_mes_%",
            "rent_efetiva": "rentabilidade_efetiva_%", "rent_patrimonial": "rentabilidade_patrimonial_%", "taxa_adm": "taxa_adm_%",
            "amortizacao": "amortizacao_%"}).to_excel(w, sheet_name="Informe mensal (CVM)", index=False)
        pd.DataFrame(f["trimestral"]).to_excel(w, sheet_name="Vacância e inadimplência", index=False)
        pd.DataFrame(f["imoveis"]).to_excel(w, sheet_name=f"Imóveis {f['imoveis_data']}"[:31], index=False)
        pd.DataFrame(f["setores_inquilinos"], columns=["setor", "%_receita"]).to_excel(w, sheet_name="Locatários por setor", index=False)
        pd.DataFrame(f["rendimentos"], columns=["data_com_ou_ex", "rendimento_por_cota", "fonte", "pagamento"]).to_excel(
            w, sheet_name="Rendimentos", index=False)
        pd.DataFrame({"data": f["cotacao"]["datas"], "fechamento": f["cotacao"]["fechamento"]}).to_excel(w, sheet_name="Cotação semanal (Yahoo)", index=False)
    (DIR_XLSX / f"{f['cadastro']['ticker']}.xlsx").write_bytes(buf.getvalue())


def exportar_secao(saida):
    if not saida["fundos"]:
        return
    ARQ_XLSX.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame(saida["fundos"]).to_excel(w, sheet_name="Planilhão", index=False)
        pd.DataFrame(saida["segmentos"]).to_excel(w, sheet_name="Segmentos (medianas)", index=False)
        pd.DataFrame([{"fonte": k, "descricao": v} for k, v in saida["fontes"].items()] +
                     [{"fonte": "gerado_em", "descricao": saida["gerado_em"]}]).to_excel(w, sheet_name="Fontes", index=False)
    ARQ_XLSX.write_bytes(buf.getvalue())


if __name__ == "__main__":
    sys.exit(1 if gerar() and not ARQ.exists() else 0)
