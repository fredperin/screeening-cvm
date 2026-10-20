"""
Eventos das empresas (CVM, dados abertos IPE): fatos relevantes, comunicados ao
mercado e avisos aos acionistas, com o link do documento oficial.

Saídas: site/dados/eventos/{id}.json (últimos 3 anos por empresa) e
site/dados/eventos_recentes.json (fatos relevantes mais recentes de todas).
Uso: py -m pipeline.eventos
"""

import io
import json
import zipfile
from datetime import date

import pandas as pd
import requests

from pipeline import DIR_DADOS_SITE
from src.screening import universo_perfis as universo_selecionado  # empresas + bancos listados

URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{ano}.zip"
CATEGORIAS = {"Fato Relevante": "fato", "Comunicado ao Mercado": "comunicado", "Aviso aos Acionistas": "aviso"}
ANOS = 3
DIR_EVENTOS = DIR_DADOS_SITE / "eventos"


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
    return len(df)


if __name__ == "__main__":
    gerar()
