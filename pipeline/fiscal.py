"""
Política fiscal (Macro → Política fiscal: Arrecadação, Despesas e Endividamento), além das séries do Banco Central
que já estão em pipeline/macro.py:

- Tesouro Nacional, Resultado do Tesouro Nacional (RTN), API Séries Temporais (aberta, sem chave): receitas,
  transferências, despesas e resultado primário do Governo Central, mensais desde 1997, R$ milhões correntes.
- Receita Federal, arrecadação das receitas federais por tributo e estado (arquivo aberto, mensal desde 2000, R$).
- Tesouro Transparente (CKAN): estoque da Dívida Pública Federal título a título (desde set/2017) e estoque do
  Tesouro Direto por título. Só baixados quando o Tesouro publica versão nova.
- SICONFI (Tesouro, API aberta): Relatório de Gestão Fiscal dos estados e das capitais — dívida consolidada líquida,
  receita corrente líquida e despesa com pessoal. Cópia local por período; só os períodos que faltam são consultados.
- Banco Central (SGS): dívida líquida por esfera (% do PIB), PIB acumulado em 12 meses e IPCA (para % do PIB e
  valores a preços de hoje).

Cada parte que falhar fica com a versão anterior. Saída: site/dados/fiscal.json.
Uso: py -m pipeline.fiscal
"""

import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests

from config.config import RAW_DIR
from pipeline import DIR_DADOS_SITE, sem_segredos
from pipeline.macro import _empacotar, baixar_sgs

ARQ = DIR_DADOS_SITE / "fiscal.json"
DIR_RAW = RAW_DIR / "fiscal"
DIR_RAW.mkdir(parents=True, exist_ok=True)
FUSO_BR = timezone(timedelta(hours=-3))
NAVEGADOR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"}
REVISAO_DIAS = 7  # mesmo com o último mês em dia, refaz uma vez por semana (revisões das fontes)

# ---------------- RTN (Tesouro) ----------------
URL_RTN = "https://apiapex.tesouro.gov.br/aria/v1/series-temporais/custom/resultado-fiscal"
RTN = {  # chave -> (código da série no RTN, nome)
    "receita_total": ("10.01.1", "Receita total"),
    "receita_liquida": ("10.01.2", "Receita líquida (receita total − transferências a estados e municípios)"),
    "transferencias": ("10.02.1", "Transferências a estados e municípios por repartição de receita"),
    "receita_rfb": ("10.01.1.1", "Receitas administradas pela Receita Federal"),
    "receita_rgps": ("10.01.1.3", "Arrecadação líquida da Previdência (RGPS)"),
    "receita_nao_adm": ("10.01.1.4", "Receitas não administradas pela Receita Federal"),
    "concessoes": ("10.01.1.4.1", "Concessões e permissões"),
    "dividendos": ("10.01.1.4.2", "Dividendos e participações"),
    "recursos_naturais": ("10.01.1.4.4", "Exploração de recursos naturais (royalties e participações)"),
    "div_bb": ("10.01.1.4.2.1", "Banco do Brasil"), "div_bndes": ("10.01.1.4.2.3", "BNDES"),
    "div_caixa": ("10.01.1.4.2.4", "Caixa"), "div_eletrobras": ("10.01.1.4.2.6", "Eletrobras"),
    "div_petrobras": ("10.01.1.4.2.8", "Petrobras"),
    "despesa_total": ("10.03.1", "Despesa total"),
    "previdencia": ("10.03.1.1", "Benefícios previdenciários"),
    "pessoal": ("10.03.1.2", "Pessoal e encargos sociais"),
    "outras_obrig": ("10.03.1.3", "Outras despesas obrigatórias"),
    "controle_fluxo": ("10.03.1.4.1", "Obrigatórias com controle de fluxo"),
    "discricionarias": ("10.03.1.4.2", "Despesas discricionárias do Poder Executivo"),
    "obr_abono": ("10.03.1.3.01", "Abono e seguro-desemprego"), "obr_bpc": ("10.03.1.3.05", "BPC (LOAS/RMV)"),
    "obr_subsidios": ("10.03.1.3.15", "Subsídios, subvenções e Proagro"), "obr_fundeb": ("10.03.1.3.10", "Fundeb (complemento da União)"),
    "obr_sentencas": ("10.03.1.3.14", "Sentenças judiciais e precatórios"), "obr_creditos": ("10.03.1.3.07", "Créditos extraordinários"),
    "obr_compensacao": ("10.03.1.3.08", "Compensação ao RGPS pela desoneração da folha"),
    "cf_bolsa": ("10.03.1.4.1.2", "Bolsa Família"), "cf_saude": ("10.03.1.4.1.3", "Saúde"), "cf_educacao": ("10.03.1.4.1.4", "Educação"),
    "disc_saude": ("10.03.1.4.2.1", "Saúde"), "disc_educacao": ("10.03.1.4.2.2", "Educação"), "disc_defesa": ("10.03.1.4.2.3", "Defesa"),
    "disc_transporte": ("10.03.1.4.2.4", "Transporte"), "disc_administracao": ("10.03.1.4.2.5", "Administração"),
    "disc_ciencia": ("10.03.1.4.2.6", "Ciência e tecnologia"), "disc_seguranca": ("10.03.1.4.2.7", "Segurança pública"),
    "disc_assistencia": ("10.03.1.4.2.8", "Assistência social"), "disc_demais": ("10.03.1.4.2.9", "Demais áreas"),
    "resultado_central": ("10.04.1", "Resultado primário do Governo Central"),
    "resultado_tesouro": ("10.04.1.1", "Tesouro Nacional"), "resultado_previdencia": ("10.04.1.2", "Previdência Social"),
    "resultado_bcb": ("10.04.1.3", "Banco Central"),
    "juros_central": ("10.08.1", "Juros nominais do Governo Central"), "nominal_central": ("10.09.1", "Resultado nominal do Governo Central"),
    "investimento": ("10.99.3.2", "Investimento do governo federal"),
}
# diferenças calculadas para as barras somadas fecharem no total
RTN_RESTOS = {
    "nao_adm_demais": ("receita_nao_adm", ["concessoes", "dividendos", "recursos_naturais"], "Demais receitas não administradas"),
    "div_demais": ("dividendos", ["div_bb", "div_bndes", "div_caixa", "div_eletrobras", "div_petrobras"], "Demais empresas"),
    "obr_demais": ("outras_obrig", ["obr_abono", "obr_bpc", "obr_subsidios", "obr_fundeb", "obr_sentencas", "obr_creditos", "obr_compensacao"],
                   "Demais obrigatórias"),
    "cf_demais": ("controle_fluxo", ["cf_bolsa", "cf_saude", "cf_educacao"], "Demais com controle de fluxo"),
}

# ---------------- Receita Federal ----------------
URL_ARRECADACAO = "https://www.gov.br/receitafederal/dados/arrecadacao-estado.csv"
MESES_PT = {m: i for i, m in enumerate(["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
                                        "outubro", "novembro", "dezembro"], start=1)}
# grupo -> (coluna do total, colunas das partes): em cada época a Receita usa ou o total ou as partes, nunca os dois
TRIBUTOS = {
    "ir": ("Imposto de Renda (IRPF, IRPJ e IRRF)", None, ["IRPF", "IRPJ - ENTIDADES FINANCEIRAS", "IRPJ - DEMAIS EMPRESAS",
           "IRRF - RENDIMENTOS DO TRABALHO", "IRRF - RENDIMENTOS DO CAPITAL", "IRRF - REMESSAS P/ EXTERIOR", "IRRF - OUTROS RENDIMENTOS"]),
    "previdencia": ("Contribuição previdenciária (RGPS)", "RECEITA PREVIDENCIÁRIA", ["RECEITA PREVIDENCIÁRIA - PRÓPRIA", "RECEITA PREVIDENCIÁRIA - DEMAIS"]),
    "cofins": ("Cofins", "COFINS", ["COFINS - FINANCEIRAS", "COFINS - DEMAIS"]),
    "pis": ("PIS/Pasep", "CONTRIBUIÇÃO PARA O PIS/PASEP", ["CONTRIBUIÇÃO PARA O PIS/PASEP - FINANCEIRAS", "CONTRIBUIÇÃO PARA O PIS/PASEP - DEMAIS"]),
    "csll": ("CSLL", "CSLL", ["CSLL - FINANCEIRAS", "CSLL - DEMAIS"]),
    "ipi": ("IPI", None, ["IPI - FUMO", "IPI - BEBIDAS", "IPI - AUTOMÓVEIS", "IPI - VINCULADO À IMPORTACAO", "IPI - OUTROS"]),
    "comercio": ("Imposto de importação e exportação", None, ["IMPOSTO SOBRE IMPORTAÇÃO", "IMPOSTO SOBRE EXPORTAÇÃO"]),
    "iof": ("IOF", None, ["IMPOSTO S/ OPERAÇÕES FINANCEIRAS"]),
    "outros_orgaos": ("Administradas por outros órgãos", None, ["ADMINISTRADAS POR OUTROS ÓRGÃOS"]),
}
# subdivisões do Imposto de Renda (tabela)
IR_PARTES = {"irpf": ("IRPF (pessoa física)", ["IRPF"]), "irpj": ("IRPJ (empresas)", ["IRPJ - ENTIDADES FINANCEIRAS", "IRPJ - DEMAIS EMPRESAS"]),
             "irrf_trabalho": ("IRRF — rendimentos do trabalho", ["IRRF - RENDIMENTOS DO TRABALHO"]),
             "irrf_capital": ("IRRF — rendimentos do capital", ["IRRF - RENDIMENTOS DO CAPITAL"]),
             "irrf_exterior": ("IRRF — remessas ao exterior", ["IRRF - REMESSAS P/ EXTERIOR"]),
             "irrf_outros": ("IRRF — outros rendimentos", ["IRRF - OUTROS RENDIMENTOS"])}

# ---------------- Tesouro Transparente: Dívida Pública Federal e Tesouro Direto ----------------
URL_CKAN = "https://www.tesourotransparente.gov.br/ckan/api/3/action/resource_show?id={}"
RECURSOS = {  # arquivo -> id do recurso no CKAN
    "estoque_dpf": "b6280ed3-ef7e-4569-954a-bded97c2c8a1",
    "estoque_td": "650cdc18-0513-4bb1-9222-003ad1c11ac7",
}
URL_RECURSO = {
    "estoque_dpf": "https://www.tesourotransparente.gov.br/ckan/dataset/0998f610-bc25-4ce3-b32c-a873447500c2/resource/b6280ed3-ef7e-4569-954a-bded97c2c8a1/download/estoquedpf.csv",
    "estoque_td": "https://www.tesourotransparente.gov.br/ckan/dataset/4d4dac3b-96d2-4011-92c9-ddf7d8392622/resource/650cdc18-0513-4bb1-9222-003ad1c11ac7/download/estoquetesourodireto.csv",
}
INDEXADOR_TITULO = [  # prefixo do título -> indexador (DPF em mercado); o resto da dívida interna fica em "demais"
    ("LFT", "selic"), ("LTN", "pre"), ("NTN-F", "pre"), ("NTN-B", "ipca"), ("NTN-C", "igpm")]
NOMES_INDEXADOR = {"selic": "Selic (LFT)", "pre": "Prefixado (LTN e NTN-F)", "ipca": "IPCA (NTN-B)", "igpm": "IGP-M (NTN-C)",
                   "cambio": "Câmbio (dívida externa)", "demais": "Demais títulos e contratos"}
TIPOS_TD = [("Selic", "Tesouro Selic"), ("Prefixado", "Tesouro Prefixado"), ("IPCA", "Tesouro IPCA+"), ("Renda", "Tesouro Renda+"),
            ("Educa", "Tesouro Educa+"), ("IGPM", "Tesouro IGPM+")]

# ---------------- SICONFI (RGF dos estados e das capitais) ----------------
URL_SICONFI = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/{}"
ANO_INICIAL_RGF = 2019
UF_IBGE = {11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO", 21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB",
           26: "PE", 27: "AL", 28: "SE", 29: "BA", 31: "MG", 32: "ES", 33: "RJ", 35: "SP", 41: "PR", 42: "SC", 43: "RS", 50: "MS",
           51: "MT", 52: "GO", 53: "DF"}

# ---------------- Banco Central (SGS) ----------------
SGS = {
    "dlsp_federal": (4503, "Governo Federal e Banco Central", "% PIB"),
    "dlsp_estados": (4507, "Governos estaduais", "% PIB"),
    "dlsp_municipios": (4508, "Governos municipais", "% PIB"),
    "dlsp_estatais": (4509, "Empresas estatais", "% PIB"),
    "pib_12m": (4382, "PIB acumulado em 12 meses (valores correntes)", "R$ milhões"),
    "ipca_mensal": (433, "IPCA — variação mensal", "%"),
}


def _get(url, tentativas=3, **kw):
    for i in range(tentativas):
        try:
            r = requests.get(url, headers=NAVEGADOR, timeout=kw.pop("timeout", 180), **kw)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if i == tentativas - 1:
                raise
            time.sleep(10 * (i + 1))


def _mes_anterior(hoje, n=1):
    m = hoje.year * 12 + hoje.month - 1 - n
    return f"{m // 12}-{m % 12 + 1:02d}"


def _precisa(controle, chave, ultimo, esperado, hoje):
    """Consulta no máximo uma vez por dia, e só se faltar o mês esperado ou na revisão semanal."""
    c = controle.setdefault(chave, {})
    if c.get("tentado_em") == hoje.isoformat():
        return False
    if not ultimo or ultimo < esperado:
        return True
    return not c.get("ok_em") or (hoje - date.fromisoformat(c["ok_em"])).days >= REVISAO_DIAS


def _soma12(s):
    return s.rolling(12).sum().dropna()


def _pct_pib(s12, pib12):
    """Valor de 12 meses em % do PIB de 12 meses do mesmo mês (sem PIB do mês, sem ponto)."""
    return (s12 / pib12.reindex(s12.index) * 100).dropna()


def _a_precos_de_hoje(mensal, ipca_mensal):
    """Valores mensais trazidos a preços do último mês do IPCA (índice encadeado da variação mensal)."""
    indice = (1 + ipca_mensal / 100).cumprod()
    indice = indice.reindex(mensal.index).ffill()
    return mensal * indice.iloc[-1] / indice


# ---------------- partes ----------------
def rtn(anterior, controle, hoje):
    ult = ((anterior.get("series") or {}).get("rtn_receita_total") or {}).get("datas", [None])[-1]
    if not _precisa(controle, "rtn", (ult or "")[:7], _mes_anterior(hoje, 2), hoje):
        return None
    controle["rtn"]["tentado_em"] = hoje.isoformat()
    regs = _get(URL_RTN, params={"tema": "10", "pageSize": 200000}, timeout=300).json().get("registros", [])
    if len(regs) < 10000:
        raise RuntimeError(f"RTN: só {len(regs)} registros (resposta incompleta?)")
    d = pd.DataFrame(regs)
    d["data"] = pd.to_datetime(d["data"].str[:10])
    tab = d.pivot_table(index="data", columns="codigoSerie", values="valor", aggfunc="last").sort_index()
    mensal = {k: tab[cod].dropna() for k, (cod, _) in RTN.items() if cod in tab}
    for k, (total, partes, _) in RTN_RESTOS.items():
        if total in mensal and all(p in mensal for p in partes):
            mensal[k] = mensal[total] - sum(mensal[p] for p in partes)
    controle["rtn"]["ok_em"] = hoje.isoformat()
    return mensal


def arrecadacao(anterior, controle, hoje):
    ult = ((anterior.get("series") or {}).get("arr_total") or {}).get("datas", [None])[-1]
    if not _precisa(controle, "receita_federal", (ult or "")[:7], _mes_anterior(hoje, 2), hoje):
        return None
    controle["receita_federal"]["tentado_em"] = hoje.isoformat()
    d = pd.read_csv(io.BytesIO(_get(URL_ARRECADACAO, timeout=180).content), sep=";", encoding="latin1", dtype=str)
    d["mes"] = d["Mês"].str.strip().str.lower().map(MESES_PT)
    if d["mes"].isna().any():
        raise RuntimeError("Receita Federal: mês não reconhecido no arquivo (layout mudou?)")
    d["data"] = pd.to_datetime(dict(year=d["Ano"].astype(int), month=d["mes"].astype(int), day=1))
    colunas = [c for c in d.columns if c not in ("Ano", "Mês", "UF", "mes", "data")]
    for c in colunas:
        d[c] = pd.to_numeric(d[c].str.replace(".", "", regex=False).str.replace(",", ".", regex=False), errors="coerce").fillna(0)
    br = d.groupby("data")[colunas].sum().sort_index() / 1e6  # R$ milhões
    faltando = [c for g in TRIBUTOS.values() for c in ([g[1]] if g[1] else []) + g[2] if c not in br]
    if any(c in faltando for g in TRIBUTOS.values() for c in g[2][:1]):
        raise RuntimeError(f"Receita Federal: colunas ausentes {faltando[:5]} (layout mudou?)")
    mensal, usadas = {}, set()
    for k, (_, total, partes) in TRIBUTOS.items():
        p = br[[c for c in partes if c in br]].sum(axis=1)
        t = br[total] if total and total in br else 0
        mensal[f"arr_{k}"] = p.where(p != 0, t) if total else p
        usadas |= set(partes) | ({total} if total else set())
    mensal["arr_outros"] = br[[c for c in colunas if c not in usadas]].sum(axis=1)
    mensal["arr_total"] = br[colunas].sum(axis=1)
    for k, (_, cols) in IR_PARTES.items():
        mensal[f"ir_{k}"] = br[[c for c in cols if c in br]].sum(axis=1)
    controle["receita_federal"]["ok_em"] = hoje.isoformat()
    return mensal


def _versao_ckan(recurso):
    return _get(URL_CKAN.format(RECURSOS[recurso]), timeout=60).json()["result"]["last_modified"]


def _baixar_ckan(recurso):
    """Arquivo do Tesouro Transparente só quando há versão nova; devolve o texto e se mudou."""
    arq, versao_arq = DIR_RAW / f"{recurso}.csv", DIR_RAW / f"{recurso}.versao"
    versao = _versao_ckan(recurso)
    if arq.exists() and versao_arq.exists() and versao_arq.read_text(encoding="utf-8") == versao:
        return arq.read_bytes(), False
    conteudo = _get(URL_RECURSO[recurso], timeout=300).content
    if conteudo[:15].lower().startswith(b"<!doctype") or b"<html" in conteudo[:200].lower():
        raise RuntimeError(f"Tesouro Transparente ({recurso}): resposta em HTML em vez do arquivo (proteção do site)")
    arq.write_bytes(conteudo)
    versao_arq.write_text(versao, encoding="utf-8")
    return conteudo, True


def divida_federal():
    conteudo, _ = _baixar_ckan("estoque_dpf")
    d = pd.read_csv(io.BytesIO(conteudo), sep=";", encoding="latin1", dtype=str)
    d.columns = ["titulo", "vencimento", "valor", "quantidade", "mes", "classe", "tipo"]
    d = d[d["classe"].str.strip() == "Mercado"].copy()
    d["valor"] = pd.to_numeric(d["valor"].str.replace(",", ".", regex=False), errors="coerce").fillna(0) / 1e6  # R$ milhões
    d["data"] = pd.to_datetime("01/" + d["mes"].str.strip(), format="%d/%m/%Y")
    d["venc"] = pd.to_datetime(d["vencimento"].str.strip(), format="%d/%m/%Y", errors="coerce")

    def indexador(linha):
        if "Externa" in linha["tipo"]:
            return "cambio"
        t = linha["titulo"].strip().upper()
        return next((ix for pref, ix in INDEXADOR_TITULO if t.startswith(pref)), "demais")
    d["ix"] = d.apply(indexador, axis=1)
    por = d.pivot_table(index="data", columns="ix", values="valor", aggfunc="sum").fillna(0).sort_index()
    mensal = {f"dpf_{ix}": por[ix] for ix in NOMES_INDEXADOR if ix in por}
    mensal["dpf_total"] = por.sum(axis=1)
    # parcela que vence nos próximos 12 meses, em cada mês
    d["em12"] = (d["venc"] <= d["data"] + pd.DateOffset(months=12)) & (d["venc"] >= d["data"])
    mensal["dpf_vence_12m"] = (d[d["em12"]].groupby("data")["valor"].sum() / mensal["dpf_total"] * 100).reindex(por.index).fillna(0)
    ult = d["data"].max()
    perfil = d[(d["data"] == ult) & (d["venc"] >= ult)].groupby(d["venc"].dt.year)["valor"].sum()
    vencimentos = {"data": ult.strftime("%Y-%m-%d"), "anos": [str(a) for a in perfil.index[:15]],
                   "valores": [round(float(v), 1) for v in perfil.values[:15]],
                   "depois": round(float(perfil.values[15:].sum()), 1)}
    return mensal, vencimentos


def tesouro_direto():
    conteudo, _ = _baixar_ckan("estoque_td")
    d = pd.read_csv(io.BytesIO(conteudo), sep=";", encoding="latin1", dtype=str)
    d.columns = [c.strip() for c in d.columns]
    d["valor"] = pd.to_numeric(d["Valor Estoque"].str.replace(",", ".", regex=False), errors="coerce").fillna(0) / 1e6
    d["data"] = pd.to_datetime("01/" + d["Mes Estoque"].str.strip(), format="%d/%m/%Y")
    tipo = d["Tipo Titulo"].str.strip()
    d["grupo"] = tipo.map(lambda t: next((k for k, nome in TIPOS_TD if t.startswith(nome)), "Outros"))
    por = d.pivot_table(index="data", columns="grupo", values="valor", aggfunc="sum").fillna(0).sort_index()
    mensal = {f"td_{k.lower()}": por[k] for k, _ in TIPOS_TD if k in por}
    if "Outros" in por:
        mensal["td_outros"] = por["Outros"]
    mensal["td_total"] = por.sum(axis=1)
    return mensal


def _rgf(ano, periodo, anexo, esfera, ente):
    """RGF de um ente num quadrimestre, com cópia local (o que já foi publicado não é pedido de novo)."""
    arq = DIR_RAW / "siconfi" / f"{esfera}{ente}_{ano}_{periodo}_{anexo[-2:]}.json"
    if arq.exists():
        return json.loads(arq.read_text(encoding="utf-8"))
    r = _get(URL_SICONFI.format("rgf"), params={"an_exercicio": ano, "in_periodicidade": "Q", "nr_periodo": periodo,
             "co_tipo_demonstrativo": "RGF", "no_anexo": anexo, "co_esfera": esfera, "co_poder": "E", "id_ente": ente}, timeout=120)
    itens = r.json().get("items", [])
    linhas = [{"c": x["cod_conta"], "col": x["coluna"], "v": x["valor"]} for x in itens
              if x["cod_conta"] in ("DividaConsolidadaLiquida", "RGF2ReceitaCorrenteLiquida", "PercentualDaDCLSobreARCL",
                                    "DespesaComPessoalTotal", "ReceitaCorrenteLiquidaAjustada")]
    if linhas:  # período ainda não publicado não é guardado (tenta de novo depois)
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(json.dumps(linhas), encoding="utf-8")
    return linhas


def _valor(linhas, conta, coluna_contem):
    return next((x["v"] for x in linhas if x["c"] == conta and coluna_contem.lower() in x["col"].lower()), None)


def entes_rgf(esfera, entes, hoje):
    """Dívida consolidada líquida (fim de cada ano desde 2019 e quadrimestres do ano corrente) e despesa com pessoal
    do último quadrimestre publicado, para cada ente."""
    periodos = [(a, 3) for a in range(ANO_INICIAL_RGF, hoje.year)] + [(hoje.year, q) for q in (1, 2, 3)]

    def um(ente):
        serie, ultimo = [], None
        for ano, q in periodos:
            if hoje.year * 12 + hoje.month <= ano * 12 + q * 4:
                continue  # o quadrimestre ainda não terminou (a publicação sai até 30 dias depois do fim)
            l2 = _rgf(ano, q, "RGF-Anexo 02", esfera, ente)
            if not l2:
                continue
            col = f"{q}º Quadrimestre"
            dcl, rcl = _valor(l2, "DividaConsolidadaLiquida", col), _valor(l2, "RGF2ReceitaCorrenteLiquida", col)
            pct = _valor(l2, "PercentualDaDCLSobreARCL", col)
            serie.append({"periodo": f"{ano}-{q}Q", "data": f"{ano}-{q * 4:02d}-01", "dcl": dcl, "rcl": rcl, "dcl_rcl": pct})
            ultimo = (ano, q)
        pessoal = None
        if ultimo:
            l1 = _rgf(*ultimo, "RGF-Anexo 01", esfera, ente)
            pessoal = next((x["v"] for x in l1 if x["c"] == "DespesaComPessoalTotal" and "%" in x["col"]), None)
        return {"serie": serie, "pessoal_rcl": pessoal}

    with ThreadPoolExecutor(max_workers=3) as ex:
        resultados = dict(zip(entes, ex.map(um, entes)))
    return resultados


def capitais():
    arq = DIR_RAW / "siconfi_capitais.json"
    if arq.exists() and (time.time() - arq.stat().st_mtime) < 180 * 86400:
        return json.loads(arq.read_text(encoding="utf-8"))
    itens = _get(URL_SICONFI.format("entes"), timeout=180).json()["items"]
    caps = {str(x["cod_ibge"]): f"{x['ente']} ({x['uf']})" for x in itens if x.get("esfera") == "M" and str(x.get("capital", "")).strip() == "1"}
    if len(caps) < 26:
        raise RuntimeError(f"SICONFI: só {len(caps)} capitais na lista de entes")
    arq.write_text(json.dumps(caps, ensure_ascii=False), encoding="utf-8")
    return caps


def _tabela_entes(res, nomes):
    linhas = []
    for ente, r in res.items():
        if not r["serie"]:
            continue
        u = r["serie"][-1]
        linhas.append({"id": str(ente), "nome": nomes[ente], "periodo": u["periodo"], "dcl": u["dcl"], "rcl": u["rcl"],
                       "dcl_rcl": u["dcl_rcl"], "pessoal_rcl": r["pessoal_rcl"],
                       "historico": {"datas": [x["data"] for x in r["serie"]], "dcl_rcl": [x["dcl_rcl"] for x in r["serie"]]}})
    return sorted(linhas, key=lambda x: -(x["dcl_rcl"] or -999))


# ---------------- montagem ----------------
def _pacote(serie, nome, unidade, casas=2):
    # crescimento sobre base zero (tributo que a Receita ainda não arrecadava) não tem valor: fica fora da série
    return _empacotar(serie.replace([float("inf"), float("-inf")], float("nan")).dropna(), nome, unidade, casas=casas)


def gerar():
    hoje = date.today()
    anterior = json.loads(ARQ.read_text(encoding="utf-8")) if ARQ.exists() else {}
    series = dict(anterior.get("series") or {})
    controle = dict(anterior.get("controle") or {})
    extras = {k: anterior.get(k) for k in ("vencimentos_dpf", "estados", "capitais")}
    falhas = []

    def parte(nome, funcao):
        try:
            return funcao()
        except Exception as e:  # noqa: BLE001 — a parte fica com a versão anterior
            falhas.append(sem_segredos(f"{nome}: {e}")[:300])
            return None

    bc = {}
    for k, (cod, nome, un) in SGS.items():
        s = parte(f"Banco Central (SGS {cod})", lambda cod=cod: baixar_sgs(cod))
        if s is not None and not s.empty:
            bc[k] = s
            if k.startswith("dlsp_"):
                series[k] = _pacote(s, nome, un)
    pib12, ipca = bc.get("pib_12m"), bc.get("ipca_mensal")

    def com12m(mensal, prefixo, nomes, unidade="R$ milhões", real=False):
        for k, s in mensal.items():
            nome = nomes.get(k, k)
            s12 = _soma12(s)
            series[f"{prefixo}{k}"] = _pacote(s, nome, unidade, 1)
            series[f"{prefixo}{k}_12m"] = _pacote(s12, f"{nome} — 12 meses", unidade, 1)
            if pib12 is not None:
                series[f"{prefixo}{k}_12m_pib"] = _pacote(_pct_pib(s12, pib12), f"{nome} — 12 meses, % do PIB", "% PIB", 2)
            if real and ipca is not None:
                r12 = _soma12(_a_precos_de_hoje(s, ipca))
                series[f"{prefixo}{k}_12m_real"] = _pacote(r12, f"{nome} — 12 meses, a preços de hoje (IPCA)", unidade, 1)
                series[f"{prefixo}{k}_cresc_real"] = _pacote((r12 / r12.shift(12) - 1) * 100, f"{nome} — crescimento real em 12 meses", "%", 2)

    m = parte("Tesouro (RTN)", lambda: rtn(anterior, controle, hoje))
    if m:
        nomes = {k: v[1] for k, v in RTN.items()} | {k: v[2] for k, v in RTN_RESTOS.items()}
        com12m(m, "rtn_", nomes)
    m = parte("Receita Federal (arrecadação)", lambda: arrecadacao(anterior, controle, hoje))
    if m:
        nomes = {f"arr_{k}": v[0] for k, v in TRIBUTOS.items()} | {"arr_outros": "Demais tributos e contribuições",
                                                                     "arr_total": "Arrecadação federal total"}
        nomes |= {f"ir_{k}": v[0] for k, v in IR_PARTES.items()}
        com12m(m, "", nomes, real=True)
    r = parte("Tesouro (Dívida Pública Federal)", divida_federal)
    if r:
        mensal, extras["vencimentos_dpf"] = r
        for k, s in mensal.items():
            nome = "Parcela que vence em 12 meses" if k == "dpf_vence_12m" else ("DPF em mercado — total" if k == "dpf_total"
                                                                                else NOMES_INDEXADOR[k.replace("dpf_", "")])
            series[k] = _pacote(s, nome, "%" if k == "dpf_vence_12m" else "R$ milhões", 2 if k == "dpf_vence_12m" else 1)
    r = parte("Tesouro (Tesouro Direto)", tesouro_direto)
    if r:
        nomes_td = {f"td_{k.lower()}": n for k, n in TIPOS_TD} | {"td_outros": "Outros", "td_total": "Tesouro Direto — total"}
        for k, s in r.items():
            series[k] = _pacote(s, nomes_td.get(k, k), "R$ milhões", 1)
    # SICONFI: semanal (o RGF é quadrimestral; períodos já publicados ficam na cópia local e não são pedidos de novo)
    tentado = (controle.get("siconfi") or {}).get("tentado_em")
    if not extras.get("estados") or not tentado or (hoje - date.fromisoformat(tentado)).days >= REVISAO_DIAS:
        controle.setdefault("siconfi", {})["tentado_em"] = hoje.isoformat()
        res = parte("SICONFI (estados)", lambda: entes_rgf("E", list(UF_IBGE), hoje))
        if res:
            extras["estados"] = _tabela_entes(res, {k: v for k, v in UF_IBGE.items()})
        caps = parte("SICONFI (lista de capitais)", capitais)
        if caps:
            res = parte("SICONFI (capitais)", lambda: entes_rgf("M", list(caps), hoje))
            if res:
                extras["capitais"] = _tabela_entes(res, caps)
        if res:
            controle["siconfi"]["ok_em"] = hoje.isoformat()

    ARQ.write_text(json.dumps({"gerado_em": datetime.now(FUSO_BR).isoformat(timespec="minutes"), "series": series, **extras,
                               "controle": controle, "falhas": falhas}, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    print(f"✅ fiscal: {len(series)} séries; {len(extras.get('estados') or [])} estados; {len(extras.get('capitais') or [])} capitais; "
          f"{len(falhas)} falhas")
    for f in falhas:
        print("   ⚠️", f)
    return ARQ


def atualizar_divida_federal():
    """Só a Dívida Pública Federal e o Tesouro Direto (Tesouro Transparente), para as rodadas de 3x por dia: o site do
    Tesouro às vezes recusa o download, e como os arquivos são mensais basta um download bem-sucedido no mês."""
    if not ARQ.exists():
        return
    d = json.loads(ARQ.read_text(encoding="utf-8"))
    falhas = [f for f in d.get("falhas", []) if not f.startswith(("Tesouro (Dívida Pública Federal)", "Tesouro (Tesouro Direto)"))]
    try:
        mensal, d["vencimentos_dpf"] = divida_federal()
        for k, s in mensal.items():
            nome = "Parcela que vence em 12 meses" if k == "dpf_vence_12m" else ("DPF em mercado — total" if k == "dpf_total"
                                                                                else NOMES_INDEXADOR[k.replace("dpf_", "")])
            d["series"][k] = _pacote(s, nome, "%" if k == "dpf_vence_12m" else "R$ milhões", 2 if k == "dpf_vence_12m" else 1)
    except Exception as e:  # noqa: BLE001
        falhas.append(sem_segredos(f"Tesouro (Dívida Pública Federal): {e}")[:300])
    try:
        nomes_td = {f"td_{k.lower()}": n for k, n in TIPOS_TD} | {"td_outros": "Outros", "td_total": "Tesouro Direto — total"}
        for k, s in tesouro_direto().items():
            d["series"][k] = _pacote(s, nomes_td.get(k, k), "R$ milhões", 1)
    except Exception as e:  # noqa: BLE001
        falhas.append(sem_segredos(f"Tesouro (Tesouro Direto): {e}")[:300])
    d["falhas"] = falhas
    ARQ.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    gerar()
