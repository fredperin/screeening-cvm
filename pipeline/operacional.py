"""
Empresas > Operacional: dados operacionais das indústrias, de fontes oficiais com arquivo ou API abertos.

Setores e fontes (todas gratuitas, sem chave):
- Energia elétrica — ONS (dados abertos, arquivos no S3 da AWS): carga mensal por subsistema, energia armazenada (EAR)
  diária por subsistema e custo marginal de operação (CMO) semanal por subsistema.
- Petróleo e gás — ANP (dados abertos): produção mensal de petróleo e de gás natural, terra e mar.
- Combustíveis — ANP (dados abertos): vendas mensais das distribuidoras por produto.
- Veículos — Fenabrave, pela série do Banco Central (SGS 7384 a 7389): emplacamentos mensais por tipo.
- Aviação — ANAC (dados estatísticos do transporte aéreo, voo a voo): passageiros, RPK, ASK e ocupação; Azul, Gol e LATAM.
- Commodities exportadas — Comex Stat (MDIC), lido do setor_externo.json (mesma consulta, sem pedido a mais):
  volume exportado e preço implícito (valor FOB ÷ peso).

Regras do projeto: número igual ao da fonte (só conversão de unidade, sempre indicada: m³ → barris, mensal → por dia);
fonte que falha mantém a versão anterior e fica em "falhas"; arquivo grande só é baixado de novo quando a fonte o
republica; cada indicador guarda a fonte, a unidade, o tipo de agregação e a data da coleta.

Saídas: site/dados/operacional.json e site/downloads/operacional.xlsx (formato longo: periodo, kpi, valor, unidade,
tipo, fonte, coletado_em).
Uso: py -m pipeline.operacional
"""

import io
import json
import sys
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests

from pipeline import DIR_DADOS_SITE, DIR_DOWNLOADS_SITE, DIR_INTERMEDIARIO, sem_segredos
from pipeline.macro import baixar_sgs

ARQ = DIR_DADOS_SITE / "operacional.json"
ARQ_XLSX = DIR_DOWNLOADS_SITE / "operacional.xlsx"
DIR_CACHE = DIR_INTERMEDIARIO / "operacional"
ARQ_META = DIR_CACHE / "arquivos.json"
FUSO_BR = timezone(timedelta(hours=-3))
INICIO = 2010
CABECALHO = {"User-Agent": "Mozilla/5.0 (R.V. Mapp; dados abertos)"}
BARRIS_POR_M3 = 6.28981  # conversão da ANP/Petrobras

S3_ONS = "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset"
ANP = "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos"
SUBSISTEMAS = {"SE": "Sudeste/Centro-Oeste", "S": "Sul", "NE": "Nordeste", "N": "Norte"}
MESES_ANP = {m: i for i, m in enumerate(["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"], 1)}
COMBUSTIVEIS = {"ÓLEO DIESEL": ("vendas_diesel", "Vendas de óleo diesel"), "GASOLINA C": ("vendas_gasolina", "Vendas de gasolina C"),
                "ETANOL HIDRATADO": ("vendas_etanol", "Vendas de etanol hidratado"),
                "QUEROSENE DE AVIAÇÃO": ("vendas_qav", "Vendas de querosene de aviação (QAV)"), "GLP": ("vendas_glp", "Vendas de GLP (gás de cozinha)")}
VEICULOS = {"veic_automoveis": (7384, "Automóveis"), "veic_comerciais_leves": (7385, "Comerciais leves"),
            "veic_caminhoes": (7386, "Caminhões"), "veic_onibus": (7387, "Ônibus"), "veic_total": (7389, "Total")}
# Produtos do Comex Stat (posição SH4) usados aqui; vêm da consulta do setor externo
COMMODITIES = {"2601": "Minério de ferro", "2709": "Petróleo bruto", "4703": "Celulose", "0202": "Carne bovina congelada",
               "0207": "Carne de frango", "1201": "Soja em grão", "1701": "Açúcar", "0901": "Café", "7207": "Aço semiacabado"}

# Setores da seção e as empresas ligadas a cada um (tickers da lista acompanhada)
SETORES = {
    "energia": ("Energia elétrica", ["AXIA3", "CMIG4", "CPLE6", "EGIE3", "ENGI11", "EQTL3", "CPFE3", "NEOE3", "TAEE11", "AURE3", "ALUP11", "SBSP3"]),
    "petroleo": ("Petróleo e gás", ["PETR4", "PRIO3", "BRAV3", "RECV3"]),
    "combustiveis": ("Distribuição de combustíveis", ["VBBR3", "UGPA3", "RAIZ4", "CSAN3"]),
    "veiculos": ("Veículos", ["RENT3", "MOVI3", "VAMO3", "TUPY3", "RAPT4", "POMO4", "LEVE3", "MYPK3"]),
    "aviacao": ("Aviação", ["AZUL4", "GOLL4", "EMBJ3"]),
    "commodities": ("Commodities exportadas", ["VALE3", "PETR4", "SUZB3", "KLBN11", "JBSS3", "MBRF3", "SLCE3", "SMTO3", "GGBR4", "CSNA3", "USIM5"]),
}


# ---------------- download só quando a fonte republica ----------------
def _meta():
    try:
        return json.loads(ARQ_META.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def baixar(url, nome, meta):
    """Arquivo da fonte com cópia local: baixa de novo só se a assinatura (Last-Modified/ETag/tamanho) mudou.
    Sem assinatura no servidor, baixa no máximo uma vez a cada 3 dias."""
    DIR_CACHE.mkdir(parents=True, exist_ok=True)
    local = DIR_CACHE / nome
    assinatura = None
    try:
        cab = requests.head(url, headers=CABECALHO, timeout=60, allow_redirects=True)
        if cab.ok:
            assinatura = "|".join(cab.headers.get(k, "") for k in ("Last-Modified", "ETag", "Content-Length")).strip("|") or None
    except requests.RequestException:
        pass
    reg = meta.get(nome, {})
    recente = reg.get("baixado_em") and (date.today() - date.fromisoformat(reg["baixado_em"])).days < 3
    if local.exists() and ((assinatura and reg.get("assinatura") == assinatura) or (not assinatura and recente)):
        return local
    r = requests.get(url, headers=CABECALHO, timeout=300)
    r.raise_for_status()
    if r.content[:200].lstrip().lower().startswith((b"<!doctype", b"<html", b"<meta")):
        raise RuntimeError(f"{nome}: resposta em HTML em vez do arquivo (proteção do site)")
    local.write_bytes(r.content)
    meta[nome] = {"assinatura": assinatura, "baixado_em": date.today().isoformat()}
    return local


def _pacote(serie, nome, unidade, tipo, fonte, casas=1, frequencia="mensal"):
    s = serie.dropna().sort_index()
    return {"nome": nome, "unidade": unidade, "tipo": tipo, "fonte": fonte, "frequencia": frequencia,
            "coletado_em": datetime.now(FUSO_BR).isoformat(timespec="minutes"),
            "datas": [d.strftime("%Y-%m-%d") for d in s.index], "valores": [round(float(v), casas) for v in s.values]}


# ---------------- energia elétrica (ONS) ----------------
def energia(meta):
    fonte = "ONS — dados abertos"
    ind = {}
    carga = pd.read_csv(baixar(f"{S3_ONS}/carga_energia_me/CARGA_MENSAL.csv", "ons_carga_mensal.csv", meta), sep=";")
    carga["id_subsistema"] = carga["id_subsistema"].str.strip()
    carga["data"] = pd.to_datetime(carga["din_instante"]).dt.to_period("M").dt.to_timestamp()
    carga = carga[carga["val_cargaenergiamwmed"] > 0]  # o mês corrente vem com 0 (ainda não fechado)
    tab = carga.pivot_table(index="data", columns="id_subsistema", values="val_cargaenergiamwmed", aggfunc="sum")
    tab = tab[tab.index.year >= INICIO]
    completos = tab.dropna()  # o SIN só soma meses com os 4 subsistemas
    ind["carga_sin"] = _pacote(completos.sum(axis=1), "Carga de energia do SIN", "MW médios", "taxa_diaria", fonte, 0)
    for sid, nome in SUBSISTEMAS.items():
        if sid in tab:
            ind[f"carga_{sid.lower()}"] = _pacote(tab[sid], f"Carga — {nome}", "MW médios", "taxa_diaria", fonte, 0)

    # Energia armazenada: arquivo por ano; os anos fechados são baixados uma vez e o corrente quando o ONS republica
    partes = []
    for ano in range(2015, date.today().year + 1):
        try:
            arq = baixar(f"{S3_ONS}/ear_subsistema_di/EAR_DIARIO_SUBSISTEMA_{ano}.csv", f"ons_ear_{ano}.csv", meta)
        except requests.HTTPError:
            continue
        partes.append(pd.read_csv(arq, sep=";"))
    ear = pd.concat(partes, ignore_index=True)
    ear["id_subsistema"] = ear["id_subsistema"].str.strip()
    ear["data"] = pd.to_datetime(ear["ear_data"])
    soma = ear.groupby("data")[["ear_verif_subsistema_mwmes", "ear_max_subsistema"]].sum()
    n = ear.groupby("data")["id_subsistema"].nunique()
    soma = soma[n >= 4]
    ind["ear_sin"] = _pacote(soma["ear_verif_subsistema_mwmes"] / soma["ear_max_subsistema"] * 100,
                             "Energia armazenada nos reservatórios do SIN", "% da capacidade", "estoque", fonte, 1, "diária")
    for sid, nome in SUBSISTEMAS.items():
        s = ear[ear["id_subsistema"] == sid].set_index("data")["ear_verif_subsistema_percentual"]
        if not s.empty:
            ind[f"ear_{sid.lower()}"] = _pacote(s, f"Energia armazenada — {nome}", "% da capacidade", "estoque", fonte, 1, "diária")

    # Custo marginal de operação (CMO): média semanal por subsistema (referência do preço da energia no curto prazo)
    partes = []
    for ano in range(2015, date.today().year + 1):
        try:
            arq = baixar(f"{S3_ONS}/cmo_se/CMO_SEMANAL_{ano}.csv", f"ons_cmo_{ano}.csv", meta)
        except requests.HTTPError:
            continue
        partes.append(pd.read_csv(arq, sep=";"))
    cmo = pd.concat(partes, ignore_index=True)
    cmo["id_subsistema"] = cmo["id_subsistema"].str.strip()
    cmo["data"] = pd.to_datetime(cmo["din_instante"])
    for sid, nome in SUBSISTEMAS.items():
        s = cmo[cmo["id_subsistema"] == sid].set_index("data")["val_cmomediasemanal"]
        s = s[~s.index.duplicated(keep="last")]
        if not s.empty:
            ind[f"cmo_{sid.lower()}"] = _pacote(s, f"Custo marginal de operação — {nome}", "R$/MWh", "razao", fonte, 2, "semanal")
    return ind


# ---------------- petróleo, gás e combustíveis (ANP) ----------------
def _anp_mensal(caminho, nome, meta, coluna):
    d = pd.read_csv(baixar(f"{ANP}/{caminho}", nome, meta), sep=";", encoding="utf-8-sig", decimal=",")
    d["data"] = pd.to_datetime(d["ANO"].astype(str) + "-" + d["MÊS"].map(MESES_ANP).astype(str) + "-01")
    d = d[d["data"].dt.year >= INICIO]
    return d, coluna


def petroleo(meta):
    fonte = "ANP — dados abertos (produção por estado e localização)"
    ind = {}
    for chave, caminho, nome, conv, unidade, titulo in (
            ("petroleo", "ppgn-el/producao-petroleo-m3.csv", "anp_petroleo.csv", BARRIS_POR_M3 / 1000, "mil barris/dia", "Produção de petróleo"),
            ("gas", "ppgn-el/producao-gas-natural-1000m3.csv", "anp_gas.csv", 1 / 1000, "milhões m³/dia", "Produção de gás natural")):
        d, col = _anp_mensal(caminho, nome, meta, "PRODUÇÃO")
        tab = d.pivot_table(index="data", columns="LOCALIZAÇÃO", values=col, aggfunc="sum")
        total = tab.sum(axis=1)
        tab, total = tab[total > 0], total[total > 0]  # o arquivo traz os meses futuros com 0
        dias = total.index.days_in_month
        ind[f"{chave}_total"] = _pacote(total * conv / dias, titulo, unidade, "taxa_diaria", fonte, 1)
        if "MAR" in tab:
            ind[f"{chave}_mar"] = _pacote(tab["MAR"] * conv / dias, f"{titulo} — mar", unidade, "taxa_diaria", fonte, 1)
        if "TERRA" in tab:
            ind[f"{chave}_terra"] = _pacote(tab["TERRA"] * conv / dias, f"{titulo} — terra", unidade, "taxa_diaria", fonte, 1)
    return ind


def combustiveis(meta):
    fonte = "ANP — dados abertos (vendas de derivados pelas distribuidoras)"
    d, col = _anp_mensal("vdpb/vendas-derivados-petroleo-e-etanol/vendas-combustiveis-m3-1990-2025.csv", "anp_vendas.csv", meta, "VENDAS")
    tab = d.pivot_table(index="data", columns="PRODUTO", values=col, aggfunc="sum")
    tab = tab[tab.sum(axis=1) > 0]
    ind = {}
    for produto, (chave, nome) in COMBUSTIVEIS.items():
        if produto in tab:
            ind[chave] = _pacote(tab[produto] / 1000, nome, "mil m³", "fluxo", fonte, 1)
    ciclo = tab.reindex(columns=["GASOLINA C", "ETANOL HIDRATADO"]).dropna()
    if not ciclo.empty:  # Ciclo Otto: gasolina C + etanol hidratado (o que move o carro flex)
        ind["vendas_ciclo_otto"] = _pacote(ciclo.sum(axis=1) / 1000, "Vendas do ciclo Otto (gasolina C + etanol hidratado)", "mil m³", "fluxo", fonte, 1)
    return ind


# ---------------- veículos (Fenabrave, pelo Banco Central) ----------------
def veiculos():
    fonte = "Fenabrave, pelo Banco Central (SGS)"
    ind = {}
    for chave, (codigo, nome) in VEICULOS.items():
        s = baixar_sgs(codigo, inicio=INICIO, janela=20)  # mensal: uma consulta só desde 2010
        if s is None or s.empty:
            continue
        s.index = pd.to_datetime(s.index).to_period("M").to_timestamp()
        ind[chave] = _pacote(s, f"Emplacamentos — {nome.lower()}" if nome != "Total" else "Emplacamentos — total", "unidades", "fluxo",
                             f"{fonte} {codigo}", 0)
    return ind


# ---------------- aviação (ANAC) ----------------
ANAC = "https://sistemas.anac.gov.br/dadosabertos/Voos%20e%20opera%C3%A7%C3%B5es%20a%C3%A9reas/Dados%20Estat%C3%ADsticos%20do%20Transporte%20A%C3%A9reo"
# grupos pelo nome da empresa no arquivo da ANAC (as subsidiárias regionais entram no grupo)
GRUPOS_AEREOS = {"azul": ("Azul", ("AZUL ",)), "gol": ("Gol", ("GOL LINHAS",)), "latam": ("LATAM", ("TAM LINHAS", "LATAM"))}


def _ler_json_em_fluxo(caminho, ao_ler):
    """O arquivo da ANAC tem ~200 MB de listas JSON: lê objeto por objeto, sem carregá-lo inteiro na memória."""
    dec = json.JSONDecoder()
    n = 0
    with open(caminho, encoding="utf-8-sig") as f:
        buf = f.read(1 << 22).lstrip()
        pos = 1 if buf.startswith("[") else 0
        while True:
            while True:
                # o arquivo é uma sequência de listas coladas ("...][..."): o fim de uma lista emenda na seguinte
                while pos < len(buf) and buf[pos] in ", \n\r\t][":
                    pos += 1
                if pos >= len(buf):
                    break
                try:
                    obj, pos_fim = dec.raw_decode(buf, pos)
                except json.JSONDecodeError:
                    break  # objeto cortado no fim do bloco: lê mais
                ao_ler(obj)
                n += 1
                pos = pos_fim
            mais = f.read(1 << 22)
            if not mais:
                return n
            buf, pos = buf[pos:] + mais, 0


def aviacao(meta):
    """Voos regulares das empresas brasileiras: passageiros pagos, RPK (demanda) e ASK (oferta), domésticos e internacionais."""
    fonte = "ANAC — dados estatísticos do transporte aéreo"
    soma = {}

    def ao_ler(o):
        if o.get("GRUPO_DE_VOO") != "REGULAR" or o.get("EMPRESA_NACIONALIDADE") != "BRASILEIRA":
            return
        nome = (o.get("EMPRESA_NOME") or "").upper()
        grupo = next((g for g, (_, prefixos) in GRUPOS_AEREOS.items() if nome.startswith(prefixos)), "outras")
        chave = (int(o["ANO"]), int(o["MES"]), "dom" if o.get("NATUREZA") == "DOMÉSTICA" else "int", grupo)
        s = soma.setdefault(chave, [0.0, 0.0, 0.0])
        for k, campo in enumerate(("PASSAGEIROS_PAGOS", "RPK", "ASK")):
            v = (o.get(campo) or "").replace(",", ".")
            s[k] += float(v) if v else 0.0

    for arquivo, nome in (("Dados_Estatisticos_2011_a_2020.json", "anac_2011_2020.json"), ("Dados_Estatisticos_2021_a_2030.json", "anac_2021_2030.json")):
        _ler_json_em_fluxo(baixar(f"{ANAC}/{arquivo}", nome, meta), ao_ler)
    d = pd.DataFrame([(pd.Timestamp(a, m, 1), nat, g, *v) for (a, m, nat, g), v in soma.items()],
                     columns=["data", "natureza", "grupo", "pax", "rpk", "ask"])
    d = d[d["data"].dt.year >= INICIO]
    ind = {}
    dom = d[d["natureza"] == "dom"].groupby(["data", "grupo"])[["pax", "rpk", "ask"]].sum().unstack("grupo").fillna(0)
    total = dom.T.groupby(level=0).sum().T  # soma das empresas por mês
    total = total[total["ask"] > 0]
    ind["aereo_pax_dom"] = _pacote(total["pax"] / 1e6, "Passageiros pagos — voos domésticos", "milhões", "fluxo", fonte, 2)
    ind["aereo_rpk_dom"] = _pacote(total["rpk"] / 1e9, "Demanda doméstica (RPK)", "bilhões de passageiros-km", "fluxo", fonte, 2)
    ind["aereo_ask_dom"] = _pacote(total["ask"] / 1e9, "Oferta doméstica (ASK)", "bilhões de assentos-km", "fluxo", fonte, 2)
    ind["aereo_ocupacao_dom"] = _pacote(total["rpk"] / total["ask"] * 100, "Taxa de ocupação doméstica (RPK ÷ ASK)", "%", "razao", fonte, 1)
    for g, (nome, _) in GRUPOS_AEREOS.items():
        if ("rpk", g) not in dom:
            continue
        rpk, ask = dom[("rpk", g)].reindex(total.index), dom[("ask", g)].reindex(total.index)
        ind[f"aereo_share_{g}"] = _pacote(rpk / total["rpk"] * 100, f"{nome} — participação na demanda doméstica (RPK)", "%", "razao", fonte, 1)
        ind[f"aereo_ocupacao_{g}"] = _pacote((rpk / ask.where(ask > 0)) * 100, f"{nome} — taxa de ocupação doméstica", "%", "razao", fonte, 1)
        ind[f"aereo_pax_{g}"] = _pacote(dom[("pax", g)].reindex(total.index) / 1e6, f"{nome} — passageiros pagos domésticos", "milhões", "fluxo", fonte, 2)
    intl = d[d["natureza"] == "int"].groupby("data")[["pax", "rpk"]].sum()
    intl = intl[intl["pax"] > 0]
    ind["aereo_pax_int"] = _pacote(intl["pax"] / 1e6, "Passageiros pagos — voos internacionais (empresas brasileiras)", "milhões", "fluxo", fonte, 2)
    return ind


# ---------------- commodities exportadas (Comex Stat, do setor externo) ----------------
def commodities():
    arq = DIR_DADOS_SITE / "setor_externo.json"
    produtos = ((json.loads(arq.read_text(encoding="utf-8")).get("comex") or {}).get("produtos") or {}) if arq.exists() else {}
    fonte = "Comex Stat (MDIC) — exportações"
    ind = {}
    for cod, nome in COMMODITIES.items():
        p = produtos.get(cod) or {}
        if not (p.get("peso") and p.get("datas")):
            continue
        fob = pd.Series(p["valores"], index=pd.to_datetime(p["datas"]))           # US$ milhões
        peso = pd.Series(p["peso"]["valores"], index=pd.to_datetime(p["peso"]["datas"]))  # mil toneladas
        ind[f"exp_vol_{cod}"] = _pacote(peso, f"{nome} — volume exportado", "mil toneladas", "fluxo", fonte, 1)
        juntos = pd.concat([fob, peso], axis=1, keys=["fob", "t"]).dropna()
        juntos = juntos[juntos["t"] > 0]
        # preço implícito = valor ÷ volume do próprio mês (US$ milhões ÷ mil t × 1000 = US$/t)
        ind[f"exp_preco_{cod}"] = _pacote(juntos["fob"] / juntos["t"] * 1000, f"{nome} — preço implícito de exportação", "US$/t (FOB)",
                                          "razao", f"{fonte} (valor FOB ÷ peso)", 1)
    return ind


# ---------------- montagem ----------------
COLETAS = {"energia": lambda m: energia(m), "petroleo": lambda m: petroleo(m), "combustiveis": lambda m: combustiveis(m),
           "veiculos": lambda m: veiculos(), "aviacao": lambda m: aviacao(m), "commodities": lambda m: commodities()}


def gerar():
    anterior = json.loads(ARQ.read_text(encoding="utf-8")) if ARQ.exists() else {}
    antes = {s["id"]: s for s in anterior.get("setores", [])}
    meta = _meta()
    setores, falhas = [], []
    for sid, (nome, empresas) in SETORES.items():
        try:
            indicadores = COLETAS[sid](meta)
            if not indicadores:
                raise RuntimeError("nenhum indicador disponível")
        except Exception as e:  # noqa: BLE001 — fonte que falha mantém a versão anterior
            falhas.append(sem_segredos(f"{nome}: {e!r}")[:300])
            if sid in antes:
                setores.append(antes[sid])
            continue
        setores.append({"id": sid, "nome": nome, "empresas": empresas, "indicadores": indicadores})
    ARQ_META.parent.mkdir(parents=True, exist_ok=True)
    ARQ_META.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    saida = {"gerado_em": datetime.now(FUSO_BR).isoformat(timespec="minutes"), "setores": setores, "falhas": falhas}
    ARQ.write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    exportar_excel(saida)
    print(f"✅ operacional: {sum(len(s['indicadores']) for s in setores)} indicadores em {len(setores)} setores; {len(falhas)} falha(s)")
    for f in falhas:
        print("   ⚠️", f)
    return falhas


def exportar_excel(saida):
    """Formato longo (uma linha por período e indicador), como no plano dos dados operacionais."""
    linhas = []
    for s in saida["setores"]:
        for k, i in s["indicadores"].items():
            for d, v in zip(i["datas"], i["valores"]):
                linhas.append({"setor": s["nome"], "periodo": d, "kpi": k, "indicador": i["nome"], "valor": v, "unidade": i["unidade"],
                               "tipo": i["tipo"], "frequencia": i["frequencia"], "fonte": i["fonte"], "coletado_em": i["coletado_em"]})
    if not linhas:
        return
    ARQ_XLSX.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame(linhas).to_excel(w, sheet_name="Operacional", index=False)
    ARQ_XLSX.write_bytes(buf.getvalue())


if __name__ == "__main__":
    sys.exit(1 if gerar() and not ARQ.exists() else 0)
