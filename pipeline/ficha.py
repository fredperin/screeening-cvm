"""
Ficha da empresa a partir dos dados abertos da CVM: Formulário de Referência (FRE)
mais recente — acionistas, free float, administração, remuneração, empregados e
auditor — e a descrição da atividade do Formulário Cadastral (FCA).

Saída: site/dados/fichas/{id}.json. CPF/CNPJ de pessoas não são publicados.
Uso: py -m pipeline.ficha
"""

import io
import json
import zipfile
from datetime import date

import pandas as pd
import requests

from pipeline import DIR_DADOS_SITE
from src.screening import universo_selecionado

URL_FRE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/fre_cia_aberta_{ano}.zip"
URL_FCA = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FCA/DADOS/fca_cia_aberta_{ano}.zip"
TABELAS_FRE = ["", "posicao_acionaria", "distribuicao_capital", "administrador_membro_conselho_fiscal",
               "remuneracao_total_orgao", "empregado_posicao_local", "auditor"]
DIR_FICHAS = DIR_DADOS_SITE / "fichas"


def _zip(url):
    r = requests.get(url, timeout=180)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return zipfile.ZipFile(io.BytesIO(r.content))


def _ler(z, nome):
    if z is None or nome not in z.namelist():
        return pd.DataFrame()
    return pd.read_csv(z.open(nome), sep=";", encoding="latin1", dtype=str)


def carregar_fre(anos):
    tabelas = {t: [] for t in TABELAS_FRE}
    for ano in anos:
        z = _zip(URL_FRE.format(ano=ano))
        for t in TABELAS_FRE:
            tabelas[t].append(_ler(z, f"fre_cia_aberta_{t + '_' if t else ''}{ano}.csv"))
    return {t: pd.concat(p, ignore_index=True) if any(len(x) for x in p) else pd.DataFrame() for t, p in tabelas.items()}


def carregar_fca(anos):
    geral, valores = [], []
    for ano in anos:
        z = _zip(URL_FCA.format(ano=ano))
        geral.append(_ler(z, f"fca_cia_aberta_geral_{ano}.csv"))
        valores.append(_ler(z, f"fca_cia_aberta_valor_mobiliario_{ano}.csv"))
    g = pd.concat(geral, ignore_index=True)
    v = pd.concat(valores, ignore_index=True)
    g = g.sort_values("Data_Referencia").drop_duplicates("CNPJ_Companhia", keep="last") if not g.empty else g
    return g, v


def _num(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _txt(v):
    return v.strip() if isinstance(v, str) and v.strip() else None


def _orgao(v):
    t = (_txt(v) or "").lower()
    if "fiscal" in t:
        return "Conselho Fiscal"
    if "diretoria" in t and "conselho" in t:
        return "Diretoria e Conselho de Administração"
    if "diretoria" in t:
        return "Diretoria"
    if "conselho" in t:
        return "Conselho de Administração"
    return _txt(v)


def _cargo(v):
    import re
    return re.sub(r"^\d+\s*-\s*", "", v).strip() if v else None


def montar_ficha(cnpj, fre, fca_geral, fca_vm, hoje):
    ficha = {"fre": None, "acionistas": [], "free_float": None, "base_acionistas": None,
             "administracao": [], "remuneracao": None, "empregados": None, "auditor": None,
             "descricao": None, "segmento": None, "site": None}

    g = fca_geral[fca_geral["CNPJ_Companhia"] == cnpj] if not fca_geral.empty else fca_geral
    if len(g):
        ficha["descricao"] = _txt(g.iloc[0].get("Descricao_Atividade"))
        ficha["site"] = _txt(g.iloc[0].get("Pagina_Web"))
    vm = fca_vm[(fca_vm["CNPJ_Companhia"] == cnpj) & (fca_vm["Mercado"] == "Bolsa")] if not fca_vm.empty else fca_vm
    if len(vm):
        ficha["segmento"] = ", ".join(sorted(vm["Segmento"].dropna().unique())) or None

    docs = fre[""]
    docs = docs[docs["CNPJ_CIA"] == cnpj] if not docs.empty else docs
    if docs.empty:
        return ficha
    docs = docs.assign(_v=pd.to_numeric(docs["VERSAO"], errors="coerce")).sort_values(["DT_REFER", "_v"])
    doc = docs.iloc[-1]
    id_doc = doc["ID_DOC"]
    ficha["fre"] = {"referencia": doc["DT_REFER"], "versao": doc["VERSAO"], "recebido": doc["DT_RECEB"], "link": doc["LINK_DOC"]}

    def do_doc(tabela):
        t = fre[tabela]
        return t[t["ID_Documento"] == id_doc] if not t.empty else t

    # Acionistas de primeiro nível (os "relacionados" são a abertura de um acionista PJ)
    pa = do_doc("posicao_acionaria")
    if len(pa):
        topo = pa[pa["ID_Acionista_Relacionado"].isna()].copy()
        topo["PCT"] = topo["Percentual_Total_Acoes_Circulacao"].map(_num)
        # "Outros" (free float) e "Ações em tesouraria" vão para o fim da lista
        topo["RESTO"] = topo["Acionista"].fillna("").str.lower().str.contains(r"^outros|tesouraria")
        topo = topo.sort_values(["RESTO", "PCT"], ascending=[True, False])
        ficha["acionistas"] = [{
            "nome": _txt(r.Acionista), "pct_total": r.PCT, "pct_on": _num(r.Percentual_Acao_Ordinaria_Circulacao),
            "pct_pn": _num(r.Percentual_Acao_Preferencial_Circulacao), "controlador": r.Acionista_Controlador == "S",
            "acordo": r.Participante_Acordo_Acionistas == "S",
        } for r in topo.head(12).itertuples() if _txt(r.Acionista)]

    dc = do_doc("distribuicao_capital")
    if len(dc):
        r = dc.iloc[-1]
        ficha["free_float"] = _num(r["Percentual_Total_Acoes_Circulacao"])
        ficha["base_acionistas"] = {"pf": _num(r["Quantidade_Acionistas_PF"]), "pj": _num(r["Quantidade_Acionistas_PJ"]),
                                    "institucionais": _num(r["Quantidade_Acionistas_Investidores_Institucionais"])}

    adm = do_doc("administrador_membro_conselho_fiscal")
    if len(adm):
        adm = adm.drop_duplicates(["Nome", "Orgao_Administracao", "Cargo_Eletivo_Ocupado"])
        ficha["administracao"] = [{
            "orgao": _orgao(r.Orgao_Administracao), "nome": _txt(r.Nome),
            "cargo": _cargo(_txt(r.Complemento_Cargo_Eletivo_Ocupado) or _txt(r.Cargo_Eletivo_Ocupado)),
            "desde": _txt(r.Data_Inicio_Primeiro_Mandato), "eleito_controlador": r.Eleito_Controlador == "Sim",
        } for r in adm.itertuples() if _txt(r.Nome)]

    rem = do_doc("remuneracao_total_orgao")
    if len(rem):
        fechados = rem[rem["Data_Fim_Exercicio_Social"] < hoje.isoformat()]
        if len(fechados):
            ultimo = fechados["Data_Fim_Exercicio_Social"].max()
            ano = fechados[fechados["Data_Fim_Exercicio_Social"] == ultimo]
            ficha["remuneracao"] = {
                "exercicio": ultimo[:4], "total": _num(ano["Total_Remuneracao"].iloc[0]),
                "orgaos": [{"orgao": _txt(r.Orgao_Administracao), "membros": _num(r.Numero_Membros),
                            "total": _num(r.Total_Remuneracao_Orgao)} for r in ano.itertuples()],
            }

    emp = do_doc("empregado_posicao_local")
    if len(emp):
        colunas = [c for c in emp.columns if c.startswith("Quantidade_")]
        ficha["empregados"] = sum(_num(v) or 0 for c in colunas for v in emp[c])

    aud = do_doc("auditor")
    if len(aud):
        vigentes = aud[aud["Data_Fim_Contratacao"].isna() & (aud["Data_Inicio_Prestacao_Servico"].fillna("") <= hoje.isoformat())]
        escolhido = (vigentes if len(vigentes) else aud).sort_values("Data_Inicio_Prestacao_Servico").iloc[-1]
        ficha["auditor"] = {"nome": _txt(escolhido["Auditor"]), "desde": _txt(escolhido["Data_Inicio_Prestacao_Servico"])}
    return ficha


def gerar():
    hoje = date.today()
    anos = [hoje.year - 1, hoje.year]
    fre = carregar_fre(anos)
    fca_geral, fca_vm = carregar_fca(anos)
    universo = universo_selecionado()
    DIR_FICHAS.mkdir(parents=True, exist_ok=True)
    com_fre = 0
    for cnpj, tickers in zip(universo["CNPJ_CIA"], universo["tickers_lista"]):
        ficha = montar_ficha(cnpj, fre, fca_geral, fca_vm, hoje)
        com_fre += ficha["fre"] is not None
        (DIR_FICHAS / f"{tickers[0]}.json").write_text(json.dumps({"id": tickers[0], **ficha}, ensure_ascii=False,
                                                                 separators=(",", ":")), encoding="utf-8")
    print(f"✅ fichas: {len(universo)} empresas, {com_fre} com Formulário de Referência")
    return com_fre


if __name__ == "__main__":
    gerar()
