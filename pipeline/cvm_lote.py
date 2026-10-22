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


CONTAS_TOTAL = {"1", "2", "3.01", "3.03", "3.05", "3.07", "3.09", "3.11"}


def consolidado_ou_individual(base: pd.DataFrame) -> pd.DataFrame:
    """
    Uma única visão por período, sempre o CONSOLIDADO quando ele existe com números.
    - Demonstração entregue zerada não vale quando há outra com números para o mesmo período:
      empresas sem controladas mandam o consolidado zerado à CVM (ex.: TIM, Sabesp até 2024)
      e o número real está no individual. Sem alternativa, fica como a fonte entregou.
    - Para cada demonstração e data de fim, se há consolidado com números em qualquer
      envio, usa só o consolidado; o individual entra apenas onde a empresa não
      consolida (aí o individual é a empresa inteira). Nunca mistura os dois no mesmo
      período. As linhas escolhidas ficam marcadas como "con" (TIPO_ORIGEM guarda a origem).
    """
    if base.empty:
        return base
    b = base.copy()
    doc = ["TIPO", "SIGLA", "FONTE", "DT_REFER", "VERSAO", "DT_FIM_EXERC", "DT_INI_EXERC"]
    # documento "com números" = alguma conta de total diferente de zero (há consolidados zerados
    # com uma ou outra linha solta preenchida, como o balanço da TIM em 2024)
    # (na DFC vale qualquer linha: há empresas pequenas com os totais da DFC zerados e o detalhe preenchido)
    total = b["CD_CONTA"].isin(CONTAS_TOTAL) | b["SIGLA"].isin(["DMPL", "DFC_MI", "DFC_MD"])
    nao_zero = pd.Series((pd.to_numeric(b["VL_CONTA"], errors="coerce").fillna(0).to_numpy() != 0) & total.to_numpy(), index=b.index)
    # (o balanço não tem data de início: a chave vazia não pode sumir do agrupamento)
    com_numero = nao_zero.groupby([b[c].astype("string").fillna("") for c in doc], dropna=False).transform("any").astype(bool)
    # por demonstração, tipo de documento (ITR/DFP) e data: o balanço de fim de ano sai do comparativo
    # do ITR seguinte, que pode ser só individual mesmo quando o DFP tinha consolidado (Bradespar 2023)
    chave = b["SIGLA"] + "|" + b["FONTE"] + "|" + b["DT_FIM_EXERC"].astype(str)
    con_real = set(chave[(b["TIPO"] == "con") & com_numero])
    ind_real = set(chave[(b["TIPO"] == "ind") & com_numero])
    tem_con = set(chave[b["TIPO"] == "con"])
    usar = (
        chave.isin(con_real) & (b["TIPO"] == "con") & com_numero                          # consolidado com números
        | ~chave.isin(con_real) & chave.isin(ind_real) & (b["TIPO"] == "ind") & com_numero  # só o individual tem números
        # nenhum dos dois com números (ex.: DFC toda zerada de holding): fica como a fonte entregou
        | ~chave.isin(con_real | ind_real) & ((b["TIPO"] == "con") | ~chave.isin(tem_con))
    )
    b = b[usar].copy()
    b["TIPO_ORIGEM"] = b["TIPO"]
    b["TIPO"] = "con"
    return b.reset_index(drop=True)


ESCALA_NUM = {"MIL": 1000, "UNIDADE": 1}


def corrigir_escala_trocada(base: pd.DataFrame) -> pd.DataFrame:
    """
    Envio com a escala marcada errada na CVM: a Padtec mandou os DFPs de 2024 e 2025 marcados
    "UNIDADE" com os números em milhares (o ativo total fica 1.000× menor que nos ITRs vizinhos).
    Para cada envio, compara o ativo total na data do próprio envio com os envios vizinhos (2 antes
    e 2 depois): se fica perto de 1.000× (ou 1/1.000×) da mediana deles, a marcação é trocada.
    Só a marcação muda; os números são os da fonte.
    """
    if base.empty:
        return base
    b = base.copy()
    corrigidos = []
    for tipo in b["TIPO"].dropna().unique():
        at = b[(b["TIPO"] == tipo) & (b["SIGLA"] == "BPA") & (b["CD_CONTA"] == "1") & (b["DT_FIM_EXERC"] == b["DT_REFER"])].copy()
        at = at.sort_values(["DT_REFER", "VERSAO"]).drop_duplicates(["FONTE", "DT_REFER", "VERSAO"], keep="last")
        at["REAIS"] = pd.to_numeric(at["VL_CONTA"], errors="coerce") * at["ESCALA_MOEDA"].map(ESCALA_NUM)
        at = at[at["REAIS"] > 0].sort_values("DT_REFER").reset_index(drop=True)
        for i, linha in at.iterrows():
            vizinhos = pd.concat([at["REAIS"].iloc[max(0, i - 2):i], at["REAIS"].iloc[i + 1:i + 3]])
            if len(vizinhos) < 2:
                continue
            razao = vizinhos.median() / linha["REAIS"]
            nova = {"UNIDADE": "MIL"} if 500 <= razao <= 2000 else {"MIL": "UNIDADE"} if 1 / 2000 <= razao <= 1 / 500 else {}
            if linha["ESCALA_MOEDA"] in nova:
                doc = (b["FONTE"] == linha["FONTE"]) & (b["DT_REFER"] == linha["DT_REFER"]) & (b["VERSAO"] == linha["VERSAO"])
                b.loc[doc, "ESCALA_MOEDA"] = nova[linha["ESCALA_MOEDA"]]
                corrigidos.append(f"{linha['FONTE']} {linha['DT_REFER']}")
    if corrigidos:
        print(f"   ↪ escala marcada errada na CVM, corrigida: {', '.join(sorted(set(corrigidos)))}")
    return b
