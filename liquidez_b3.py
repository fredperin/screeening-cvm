"""
Liquidez mensal das ações da B3 (consulta avulsa, fora do pipeline da R.V. Mapp).

Fonte: Séries Históricas da B3 (arquivos COTAHIST anuais).
Medida: volume financeiro médio diário do mês =
        volume financeiro negociado no mês / número de pregões do mês.

Filtros:
  - mercado à vista, lote padrão (TPMERC 010); fracionário fica de fora
  - só ações e units (classe do ISIN: ACN, CDA, UNT); ficam de fora
    FIIs, ETFs, BDRs, direitos e recibos

Uso:
    python liquidez_b3.py               # 2013 até o ano corrente
    python liquidez_b3.py 2013 2020     # intervalo de anos
    python liquidez_b3.py --rebaixar    # baixa de novo também os anos já guardados

Saída: data/processed/liquidez_mensal_b3.xlsx
"""
import io
import sys
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import requests

URL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{ano}.ZIP"
PASTA_CACHE = Path("data/raw/cotahist")
SAIDA = Path("data/processed/liquidez_mensal_b3.xlsx")
CLASSES_ACAO = {"ACN", "CDA", "UNT"}


def baixar(ano, rebaixar=False):
    PASTA_CACHE.mkdir(parents=True, exist_ok=True)
    arq = PASTA_CACHE / f"COTAHIST_A{ano}.ZIP"
    # o ano corrente sempre é baixado de novo, porque o arquivo cresce a cada pregão
    if arq.exists() and not rebaixar and ano < date.today().year:
        return arq
    print(f"  baixando {ano}...", flush=True)
    r = requests.get(URL.format(ano=ano), timeout=300)
    r.raise_for_status()
    zipfile.ZipFile(io.BytesIO(r.content))  # confere se veio um zip válido
    arq.write_bytes(r.content)
    return arq


def ler(arq):
    """Lê o layout de largura fixa e devolve as linhas de ações do mercado à vista."""
    linhas = []
    pregoes = set()
    with zipfile.ZipFile(arq) as z, z.open(z.namelist()[0]) as f:
        for raw in f:
            l = raw.decode("latin-1")
            if l[:2] != "01":
                continue
            data = l[2:10]
            pregoes.add(data)
            if l[24:27] != "010" or l[236:239] not in CLASSES_ACAO:
                continue
            linhas.append((
                data,
                l[12:24].strip(),          # ticker
                l[27:39].strip(),          # nome resumido
                l[230:242],                # ISIN
                int(l[147:152]),           # número de negócios
                int(l[170:188]) / 100,     # volume financeiro (2 casas implícitas)
            ))
    df = pd.DataFrame(linhas, columns=["data", "ticker", "empresa", "isin", "negocios", "volume"])
    df["data"] = pd.to_datetime(df["data"], format="%Y%m%d")
    pregoes = pd.to_datetime(pd.Series(sorted(pregoes)), format="%Y%m%d")
    return df, pregoes


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    rebaixar = "--rebaixar" in sys.argv
    ano_ini = int(args[0]) if args else 2013
    ano_fim = int(args[1]) if len(args) > 1 else date.today().year

    partes, todos_pregoes = [], []
    for ano in range(ano_ini, ano_fim + 1):
        print(f"{ano}:", flush=True)
        df, pregoes = ler(baixar(ano, rebaixar))
        print(f"  {len(df):,} linhas de ações, {len(pregoes)} pregões", flush=True)
        partes.append(df)
        todos_pregoes.append(pregoes)

    df = pd.concat(partes, ignore_index=True)
    pregoes = pd.concat(todos_pregoes)
    df["mes"] = df["data"].dt.to_period("M")
    pregoes_mes = pregoes.dt.to_period("M").value_counts().rename("pregoes_mes")

    base = (df.groupby(["ticker", "mes"])
              .agg(volume_total=("volume", "sum"),
                   negocios=("negocios", "sum"),
                   dias_com_negocio=("data", "nunique"))
              .reset_index()
              .join(pregoes_mes, on="mes"))
    base["volume_medio_diario"] = base["volume_total"] / base["pregoes_mes"]

    # nome e ISIN mais recentes de cada ticker
    ultimo = (df.sort_values("data").groupby("ticker").last()[["empresa", "isin"]])

    tabela = base.pivot(index="ticker", columns="mes", values="volume_medio_diario")
    tabela.columns = [str(c) for c in tabela.columns]
    tabela = ultimo.join(tabela, how="right")

    base["mes"] = base["mes"].astype(str)
    ultima_data = df["data"].max().date()

    notas = pd.DataFrame({"Notas": [
        "Fonte: B3, Séries Históricas (arquivos COTAHIST anuais).",
        "Volume médio diário = volume financeiro negociado no mês / número de pregões do mês (R$).",
        "Mês sem valor = ação sem negócio no mês (ou ainda não listada / já deslistada).",
        "Mercado à vista, lote padrão; o fracionário não está incluído.",
        "Só ações e units (ISIN classe ACN, CDA, UNT); sem FIIs, ETFs, BDRs, direitos e recibos.",
        "Ticker como negociado em cada mês: trocas de código aparecem como linhas separadas (o ISIN ajuda a ligar).",
        f"Último pregão no arquivo: {ultima_data:%d/%m/%Y} (o último mês pode estar incompleto).",
    ]})

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(SAIDA, engine="openpyxl") as xl:
        tabela.to_excel(xl, sheet_name="Volume medio diario")
        base.to_excel(xl, sheet_name="Base mensal", index=False)
        notas.to_excel(xl, sheet_name="Notas", index=False)
    print(f"\nOK: {len(tabela)} tickers, {tabela.shape[1] - 2} meses -> {SAIDA}")


if __name__ == "__main__":
    main()
