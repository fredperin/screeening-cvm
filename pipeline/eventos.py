"""
Eventos das empresas (CVM, dados abertos IPE): fatos relevantes, comunicados ao
mercado e avisos aos acionistas, com o link do documento oficial.

Fatos relevantes do dia: o arquivo de dados abertos (IPE) é atualizado pela CVM com dias de atraso (em 12/11/2026 ia só até 06/11).
Por isso, a atualização diária e as atualizações ao longo do dia (pipeline/intradia.py, 5x nos dias úteis) buscam também os fatos
relevantes dos últimos dias na consulta de documentos da própria CVM (RAD, a mesma do site da CVM; uma consulta para todas as
empresas). Ficam guardados em data/pipeline/fatos_rad.json até entrarem no arquivo IPE; o número de protocolo evita repetição.

Saídas: site/dados/eventos/{id}.json (últimos 3 anos por empresa) e
site/dados/eventos_recentes.json (fatos relevantes mais recentes de todas).
Uso: py -m pipeline.eventos  |  py -m pipeline.eventos --rad (só os fatos relevantes dos últimos dias)
"""

import io
import json
import re
import sys
import zipfile
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests

from pipeline import DIR_DADOS_SITE, DIR_INTERMEDIARIO
from src.screening import universo_perfis as universo_selecionado  # empresas + bancos listados

URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{ano}.zip"
CATEGORIAS = {"Fato Relevante": "fato", "Comunicado ao Mercado": "comunicado", "Aviso aos Acionistas": "aviso"}
ANOS = 3
DIR_EVENTOS = DIR_DADOS_SITE / "eventos"
URL_RAD = "https://www.rad.cvm.gov.br/ENET/frmConsultaExternaCVM.aspx/ListarDocumentos"
LINK_RAD = ("https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&descTipo=IPE&CodigoInstituicao=1"
            "&numProtocolo={protocolo}&numSequencia={sequencia}&numVersao={versao}")
ARQ_RAD = DIR_INTERMEDIARIO / "fatos_rad.json"
DIAS_RAD = 5          # fatos relevantes dos últimos 5 dias na consulta RAD (cobre fim de semana e feriado)
GUARDAR_RAD = 30      # dias que um fato da RAD fica guardado esperando entrar no arquivo IPE
FUSO_BR = timezone(timedelta(hours=-3))


def baixar_ano(ano):
    r = requests.get(URL.format(ano=ano), timeout=120)
    if r.status_code == 404:
        return pd.DataFrame()
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        return pd.read_csv(z.open(z.namelist()[0]), sep=";", encoding="latin1", dtype=str)


def _texto(v):
    return v.strip() if isinstance(v, str) and v.strip() else None


def gerar():
    universo = universo_selecionado()
    id_por_cnpj = {c: ts[0] for c, ts in zip(universo["CNPJ_CIA"], universo["tickers_lista"])}
    hoje = date.today()
    partes = [baixar_ano(a) for a in range(hoje.year - ANOS + 1, hoje.year + 1)]
    df = pd.concat([p for p in partes if not p.empty], ignore_index=True)
    df = df[df["Categoria"].isin(CATEGORIAS) & df["CNPJ_Companhia"].isin(id_por_cnpj)].copy()
    # Mesma entrega reapresentada aparece com versões diferentes: fica a mais recente
    df["Versao"] = pd.to_numeric(df["Versao"], errors="coerce").fillna(1)
    df = df.sort_values("Versao").drop_duplicates("Protocolo_Entrega", keep="last")
    df = df.sort_values(["Data_Entrega", "Protocolo_Entrega"], ascending=False)

    DIR_EVENTOS.mkdir(parents=True, exist_ok=True)
    recentes = []
    for cnpj, grupo in df.groupby("CNPJ_Companhia"):
        id_ = id_por_cnpj[cnpj]
        eventos = [{
            "data": r.Data_Entrega[:10], "referencia": _texto(r.Data_Referencia),
            "categoria": CATEGORIAS[r.Categoria], "tipo": _texto(r.Tipo), "especie": _texto(r.Especie),
            "assunto": _texto(r.Assunto) or _texto(r.Tipo) or r.Categoria, "link": _texto(r.Link_Download),
        } for r in grupo.itertuples()]
        (DIR_EVENTOS / f"{id_}.json").write_text(json.dumps({"id": id_, "eventos": eventos}, ensure_ascii=False,
                                                            separators=(",", ":")), encoding="utf-8")
        recentes += [{"id": id_, **e} for e in eventos if e["categoria"] == "fato"]

    recentes.sort(key=lambda e: e["data"], reverse=True)
    (DIR_DADOS_SITE / "eventos_recentes.json").write_text(json.dumps(
        {"gerado_em": hoje.isoformat(), "eventos": recentes[:80]}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"✅ eventos: {df['CNPJ_Companhia'].nunique()} empresas, {len(df)} documentos "
          f"({(df['Categoria'] == 'Fato Relevante').sum()} fatos relevantes)")
    try:  # fatos relevantes que o arquivo IPE ainda não trouxe (falha aqui não derruba o histórico)
        atualizar_fatos_do_dia(universo)
    except Exception as e:  # noqa: BLE001
        print("⚠️ fatos relevantes do dia (RAD):", repr(e)[:300])
    return len(df)


# ---------------- fatos relevantes do dia: consulta de documentos da CVM (RAD) ----------------
def _protocolo(link):
    m = re.search(r"numProtocolo=(\d+)", link or "")
    return m.group(1) if m else None


def _sem_tags(s):
    return re.sub(r"<[^>]+>", "", s or "").strip(" -")


def buscar_rad(dias=DIAS_RAD):
    """Fatos relevantes entregues à CVM nos últimos `dias` dias, de todas as companhias (uma consulta)."""
    hoje = datetime.now(FUSO_BR).date()
    corpo = {"dataDe": (hoje - timedelta(days=dias)).strftime("%d/%m/%Y"), "dataAte": hoje.strftime("%d/%m/%Y"), "empresa": "",
             "setorAtividade": "-1", "categoriaEmissor": "-1", "situacaoEmissor": "-1", "tipoParticipante": "1", "dataReferencia": "",
             "categoria": "IPE_4_-1_-1", "periodo": "2", "horaIni": "", "horaFim": "", "palavraChave": "", "ultimaDtRef": "false",
             "tipoEmpresa": "0", "token": "", "versaoCaptcha": ""}
    r = requests.post(URL_RAD, json=corpo, timeout=60, headers={"User-Agent": "Mozilla/5.0 (R.V. Mapp; dados abertos)"})
    r.raise_for_status()
    d = r.json()["d"]
    if d.get("temErro"):
        raise RuntimeError(f"RAD: {d.get('msgErro')}")
    saida = []
    for linha in (d.get("dados") or "").split("&*"):
        c = linha.split("$&")
        if len(c) < 9 or c[2].strip() != "Fato Relevante":
            continue
        m = re.search(r"OpenDownloadDocumentos\('(\d+)','(\d+)','(\d+)'", linha)
        entrega = re.search(r"(\d{2})/(\d{2})/(\d{4})(?: (\d{2}:\d{2}))?", _sem_tags(c[6]))
        if not m or not entrega:
            continue
        sequencia, versao, protocolo = m.groups()  # código CVM: "00650-5" = 6505
        ref = re.search(r"(\d{2})/(\d{2})/(\d{4})", _sem_tags(c[5]))
        saida.append({"cd_cvm": int(c[0].replace("-", "").strip()), "data": f"{entrega[3]}-{entrega[2]}-{entrega[1]}", "hora": entrega[4],
                      "referencia": f"{ref[3]}-{ref[2]}-{ref[1]}" if ref else None, "assunto": _sem_tags(c[4]) or "Fato Relevante",
                      "situacao": c[7].strip(), "protocolo": protocolo,
                      "link": LINK_RAD.format(protocolo=protocolo, sequencia=sequencia, versao=versao)})
    return saida


def atualizar_fatos_do_dia(universo=None):
    """Busca os fatos relevantes recentes na RAD, guarda-os até entrarem no arquivo IPE e os junta à lista do site
    (eventos_recentes.json e eventos/{id}.json), sem repetir o que já está lá (mesmo protocolo)."""
    universo = universo if universo is not None else universo_selecionado()
    id_por_cnpj = {c: ts[0] for c, ts in zip(universo["CNPJ_CIA"], universo["tickers_lista"])}
    from config.config import RAW_DIR
    cad = pd.read_csv(RAW_DIR / "cad_cia_aberta.csv", sep=";", encoding="latin1", dtype=str, usecols=["CNPJ_CIA", "CD_CVM"])
    id_por_cd = {int(cd): id_por_cnpj[cnpj] for cnpj, cd in zip(cad["CNPJ_CIA"], cad["CD_CVM"])
                 if cnpj in id_por_cnpj and str(cd).isdigit()}
    try:
        guardados = json.loads(ARQ_RAD.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        guardados = []
    novos = [f for f in buscar_rad() if f["situacao"].lower().startswith("ativo") and f["cd_cvm"] in id_por_cd]
    por_prot = {f["protocolo"]: f for f in guardados} | {f["protocolo"]: {**f, "id": id_por_cd[f["cd_cvm"]]} for f in novos}
    corte = (date.today() - timedelta(days=GUARDAR_RAD)).isoformat()
    guardados = sorted((f for f in por_prot.values() if f["data"] >= corte), key=lambda f: (f["data"], f.get("hora") or ""), reverse=True)
    ARQ_RAD.parent.mkdir(parents=True, exist_ok=True)
    ARQ_RAD.write_text(json.dumps(guardados, ensure_ascii=False), encoding="utf-8")

    arq_rec = DIR_DADOS_SITE / "eventos_recentes.json"
    rec = json.loads(arq_rec.read_text(encoding="utf-8")) if arq_rec.exists() else {"eventos": []}
    ja = {_protocolo(e.get("link")) for e in rec["eventos"]}
    entrou = 0
    for f in guardados:
        evento = {"data": f["data"], "hora": f.get("hora"), "referencia": f["referencia"], "categoria": "fato", "tipo": None, "especie": None,
                  "assunto": f["assunto"], "link": f["link"], "fonte": "RAD"}
        if f["protocolo"] not in ja:
            rec["eventos"].append({"id": f["id"], **evento})
            entrou += 1
        arq_emp = DIR_EVENTOS / f"{f['id']}.json"
        emp = json.loads(arq_emp.read_text(encoding="utf-8")) if arq_emp.exists() else {"id": f["id"], "eventos": []}
        if f["protocolo"] not in {_protocolo(e.get("link")) for e in emp["eventos"]}:
            emp["eventos"] = sorted(emp["eventos"] + [evento], key=lambda e: e["data"], reverse=True)
            DIR_EVENTOS.mkdir(parents=True, exist_ok=True)
            arq_emp.write_text(json.dumps(emp, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    rec["eventos"] = sorted(rec["eventos"], key=lambda e: (e["data"], e.get("hora") or ""), reverse=True)[:80]
    rec["atualizado_em"] = datetime.now(FUSO_BR).isoformat(timespec="minutes")
    arq_rec.write_text(json.dumps(rec, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"✅ fatos relevantes do dia (CVM RAD): {len(novos)} das empresas acompanhadas nos últimos {DIAS_RAD} dias; {entrou} novos na lista")
    return entrou


if __name__ == "__main__":
    if "--rad" in sys.argv:
        atualizar_fatos_do_dia()
    else:
        gerar()
