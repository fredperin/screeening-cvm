"""
Leitura em lote da CVM: cada ZIP anual (ITR e DFP) é lido UMA vez e as linhas
das empresas selecionadas vão para um Parquet por ano/fonte. Depois, os dados
de uma empresa saem desses Parquets em vez de reabrir os ZIPs (que é o que
tornava inviável gerar 251 empresas com histórico completo).

Um ZIP só é baixado de novo quando a CVM o republica (Last-Modified/tamanho
mudaram) — na prática, os anos corrente e anterior, quando sai ITR/DFP novo
ou uma reapresentação.
"""

import hashlib
import json
import re
import zipfile
from datetime import date

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import requests

from config.config import CVM_BASE_URL, CVM_BASE_URL_DFP, RAW_DIR
from pipeline import DIR_INTERMEDIARIO

ANO_INICIAL = 2011
SIGLAS = ("BPA", "BPP", "DRE", "DFC_MI")
TIPOS = ("con", "ind")
COLUNAS = [
    "CNPJ_CIA", "DT_REFER", "VERSAO", "DENOM_CIA", "CD_CVM", "GRUPO_DFP", "MOEDA", "ESCALA_MOEDA",
    "ORDEM_EXERC", "DT_INI_EXERC", "DT_FIM_EXERC", "CD_CONTA", "DS_CONTA", "VL_CONTA", "ST_CONTA_FIXA",
]
DIR_CVM = DIR_INTERMEDIARIO / "cvm"
ARQ_META = RAW_DIR / "cvm_zips_meta.json"


def _url_zip(ano, fonte):
    base = CVM_BASE_URL if fonte == "ITR" else CVM_BASE_URL_DFP
    return f"{base}/{fonte.lower()}_cia_aberta_{ano}.zip"


def _caminho_zip(ano, fonte):
    return RAW_DIR / f"{fonte.lower()}_cia_aberta_{ano}.zip"


def _caminho_parquet(ano, fonte):
    return DIR_CVM / f"{fonte.lower()}_{ano}.parquet"


def baixar_se_mudou(ano: int, fonte: str, meta: dict) -> tuple:
    """Retorna (caminho_zip | None, mudou). None = a CVM ainda não publicou esse ano."""
    chave = f"{fonte}_{ano}"
    url = _url_zip(ano, fonte)
    cab = requests.head(url, timeout=60)
    if cab.status_code == 404:
        return None, False
    cab.raise_for_status()
    assinatura = f"{cab.headers.get('Last-Modified')}|{cab.headers.get('Content-Length')}"

    caminho = _caminho_zip(ano, fonte)
    if caminho.exists() and meta.get(chave) == assinatura:
        return caminho, False

    print(f"📥 {fonte} {ano}: baixando (novo ou republicado pela CVM)")
    with requests.get(url, timeout=300, stream=True) as resp:
        resp.raise_for_status()
        with open(caminho, "wb") as f:
            for parte in resp.iter_content(chunk_size=1 << 20):
                f.write(parte)
    meta[chave] = assinatura
    return caminho, True


def _ler_zip_filtrado(caminho_zip, ano, fonte, cnpjs: set) -> pd.DataFrame:
    partes = []
    with zipfile.ZipFile(caminho_zip) as z:
        nomes = set(z.namelist())
        for sigla in SIGLAS:
            for tipo in TIPOS:
                nome = f"{fonte.lower()}_cia_aberta_{sigla}_{tipo}_{ano}.csv"
                if nome not in nomes:
                    continue
                with z.open(nome) as f:
                    df = pd.read_csv(f, sep=";", encoding="latin1", decimal=".", dtype=str)
                df["CNPJ_CIA"] = df["CNPJ_CIA"].str.replace(r"\D", "", regex=True)
                df = df[df["CNPJ_CIA"].isin(cnpjs)]
                if df.empty:
                    continue
                df = df.reindex(columns=COLUNAS)
                df["FONTE"], df["ANO"], df["SIGLA"], df["TIPO"] = fonte, ano, sigla, tipo
                partes.append(df)
    if not partes:
        return pd.DataFrame()
    df = pd.concat(partes, ignore_index=True)
    df["VL_CONTA"] = pd.to_numeric(df["VL_CONTA"], errors="coerce")
    df["VERSAO"] = pd.to_numeric(df["VERSAO"], errors="coerce").astype("Int64")
    df["ANO"] = df["ANO"].astype("int16")
    return df.sort_values(["CNPJ_CIA", "SIGLA", "TIPO"]).reset_index(drop=True)


def atualizar_base_cvm(cnpjs: set, forcar: bool = False) -> list:
    """
    Garante um Parquet por ano/fonte com as empresas de `cnpjs` (só dígitos).
    Retorna a lista de (fonte, ano) reprocessados nesta execução.
    """
    DIR_CVM.mkdir(parents=True, exist_ok=True)
    meta = json.loads(ARQ_META.read_text()) if ARQ_META.exists() else {}
    assinatura_cnpjs = hashlib.sha1(",".join(sorted(cnpjs)).encode()).hexdigest()
    lista_mudou = meta.get("_empresas") != assinatura_cnpjs

    reprocessados = []
    for fonte in ("ITR", "DFP"):
        for ano in range(ANO_INICIAL, date.today().year + 1):
            caminho_zip, mudou = baixar_se_mudou(ano, fonte, meta)
            if caminho_zip is None:
                continue
            destino = _caminho_parquet(ano, fonte)
            if destino.exists() and not (mudou or forcar or lista_mudou):
                continue
            df = _ler_zip_filtrado(caminho_zip, ano, fonte, cnpjs)
            if df.empty:
                continue
            pq.write_table(pa.Table.from_pandas(df, preserve_index=False), destino, row_group_size=50_000)
            reprocessados.append((fonte, ano))
            print(f"✅ {fonte} {ano}: {len(df):,} linhas")
            ARQ_META.write_text(json.dumps(meta, indent=1))

    meta["_empresas"] = assinatura_cnpjs
    ARQ_META.write_text(json.dumps(meta, indent=1))
    return reprocessados


_DATASET = None


def carregar_empresa(cnpj: str) -> pd.DataFrame:
    """Todas as linhas (todos os anos, ITR e DFP) de uma empresa, a partir dos Parquets."""
    global _DATASET
    if _DATASET is None:
        _DATASET = ds.dataset(sorted(str(p) for p in DIR_CVM.glob("*.parquet")), format="parquet")
    alvo = re.sub(r"\D", "", cnpj)
    return _DATASET.to_table(filter=ds.field("CNPJ_CIA") == alvo).to_pandas()
