"""
cvm_itr.py — Busca e estrutura dados do ITR (Informações Trimestrais) da CVM.

Fonte: dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{ano}.zip
O ZIP anual contém, para TODAS as companhias abertas, um CSV por demonstração
(BPA, BPP, DRE, DFC_MI, DMPL, etc.) em formato "longo" (uma linha por conta/período).

Este módulo baixa o ZIP do ano (com cache local), extrai apenas o CSV da
demonstração pedida, filtra pelo CNPJ da empresa e pivota para um formato
de planilha (contas nas linhas, períodos nas colunas).
"""

import re
import time
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from config.config import (
    CVM_BASE_URL, CVM_BASE_URL_DFP, CVM_BASE_URL_CAD, CVM_BASE_URL_FCA, RAW_DIR, DEMONSTRACOES_ITR,
)

_BASE_URL_POR_FONTE = {"ITR": CVM_BASE_URL, "DFP": CVM_BASE_URL_DFP}
_PREFIXO_POR_FONTE = {"ITR": "itr", "DFP": "dfp"}


def _normalizar_cnpj(cnpj: str) -> str:
    """Remove tudo que não for dígito de um CNPJ."""
    return re.sub(r"\D", "", cnpj or "")


def _caminho_zip(ano: int, fonte: str = "ITR") -> Path:
    prefixo = _PREFIXO_POR_FONTE[fonte]
    return RAW_DIR / f"{prefixo}_cia_aberta_{ano}.zip"


def baixar_zip_ano(ano: int, fonte: str = "ITR", forcar: bool = False) -> Path:
    """
    Baixa o ZIP anual da CVM (ITR = trimestral, DFP = anual), com cache em data/raw/.
    O arquivo é grande (pode passar de 800 MB), por isso só baixa uma vez por ano/fonte.

    Args:
        ano:     ano de referência (ex: 2024)
        fonte:   "ITR" (trimestral, default) ou "DFP" (anual)
        forcar:  se True, baixa novamente mesmo que já exista em cache
    Returns:
        Path do arquivo ZIP local
    """
    caminho = _caminho_zip(ano, fonte)
    if caminho.exists() and not forcar:
        print(f"📁 Usando cache: {caminho}")
        return caminho

    prefixo = _PREFIXO_POR_FONTE[fonte]
    url = f"{_BASE_URL_POR_FONTE[fonte]}/{prefixo}_cia_aberta_{ano}.zip"
    print(f"📥 Baixando {url} ...")
    resp = requests.get(url, timeout=120, stream=True)
    resp.raise_for_status()

    with open(caminho, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)

    print(f"✅ Salvo em {caminho}")
    return caminho


_BASE_PRE_CARREGADA = None


def usar_base_pre_carregada(base) -> None:
    """
    Faz _ler_demonstracao() ler de um DataFrame já em memória (linhas de UMA empresa,
    com as colunas extras FONTE, ANO, SIGLA e TIPO) em vez de abrir o ZIP da CVM.
    Usado pelo pipeline em lote; None volta ao comportamento normal.
    """
    global _BASE_PRE_CARREGADA
    _BASE_PRE_CARREGADA = base


def _ler_demonstracao(ano: int, sigla: str, tipo: str, cnpj: str, fonte: str = "ITR") -> pd.DataFrame:
    """
    Lê e filtra por CNPJ uma demonstração específica (ex: BPA_con) de dentro do ZIP anual,
    sem extrair o arquivo inteiro para disco.

    Args:
        ano:    ano de referência
        sigla:  BPA, BPP, DRE, DFC_MI ou DMPL
        tipo:   "con" (consolidado) ou "ind" (individual)
        cnpj:   CNPJ da empresa (com ou sem formatação)
        fonte:  "ITR" (trimestral) ou "DFP" (anual)
    Returns:
        DataFrame filtrado, já com CNPJ_CIA normalizado
    """
    if _BASE_PRE_CARREGADA is not None:
        b = _BASE_PRE_CARREGADA
        df = b[(b["FONTE"] == fonte) & (b["ANO"] == ano) & (b["SIGLA"] == sigla) & (b["TIPO"] == tipo)]
        # Colunas que não existem nessa demonstração (ex: DT_INI_EXERC no Balanço) vêm
        # 100% vazias do Parquet combinado e precisam sair, como no CSV original.
        return df.drop(columns=["FONTE", "ANO", "SIGLA", "TIPO"]).dropna(axis=1, how="all").reset_index(drop=True)

    try:
        caminho_zip = baixar_zip_ano(ano, fonte)
    except requests.exceptions.HTTPError:
        print(f"   ↪ {fonte} de {ano} ainda não publicado pela CVM")
        return pd.DataFrame()

    prefixo = _PREFIXO_POR_FONTE[fonte]
    nome_csv = f"{prefixo}_cia_aberta_{sigla}_{tipo}_{ano}.csv"
    cnpj_alvo = _normalizar_cnpj(cnpj)

    with zipfile.ZipFile(caminho_zip) as z:
        if nome_csv not in z.namelist():
            print(f"⚠️ {nome_csv} não encontrado no ZIP de {ano}")
            return pd.DataFrame()

        # Lê em blocos (chunks) porque os CSVs consolidados chegam a ~190 MB
        # e cobrem todas as ~500 companhias abertas — não vale a pena carregar
        # tudo em memória só para filtrar uma empresa.
        partes = []
        with z.open(nome_csv) as f:
            leitor = pd.read_csv(
                f, sep=";", encoding="latin1", decimal=".",
                dtype={"CNPJ_CIA": str}, chunksize=200_000,
            )
            for bloco in leitor:
                bloco["CNPJ_CIA"] = bloco["CNPJ_CIA"].apply(_normalizar_cnpj)
                partes.append(bloco[bloco["CNPJ_CIA"] == cnpj_alvo])

    df = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
    if df.empty:
        print(f"⚠️ Nenhum dado de {sigla}_{tipo} para CNPJ {cnpj} em {ano}")
    return df


def buscar_cnpj(nome_empresa: str, ano: int) -> pd.DataFrame:
    """
    Busca o CNPJ de uma empresa pelo nome (busca parcial, case-insensitive)
    usando o arquivo cadastral do ITR do ano informado.
    """
    caminho_zip = baixar_zip_ano(ano)
    nome_csv = f"itr_cia_aberta_{ano}.csv"

    with zipfile.ZipFile(caminho_zip) as z:
        with z.open(nome_csv) as f:
            df = pd.read_csv(f, sep=";", encoding="latin1", dtype=str)

    resultado = df[df["DENOM_CIA"].str.upper().str.contains(nome_empresa.upper(), na=False)]
    return resultado[["CNPJ_CIA", "DENOM_CIA", "CD_CVM"]].drop_duplicates()


def listar_todas_empresas(ano: int) -> pd.DataFrame:
    """
    Lista todas as companhias abertas que enviaram ITR num ano (nome oficial
    + CNPJ), ordenadas por nome. Usada para popular uma lista de seleção
    (ex: numa interface) em vez de depender de o usuário acertar o nome.
    """
    caminho_zip = baixar_zip_ano(ano)
    nome_csv = f"itr_cia_aberta_{ano}.csv"

    with zipfile.ZipFile(caminho_zip) as z:
        with z.open(nome_csv) as f:
            df = pd.read_csv(f, sep=";", encoding="latin1", dtype=str)

    empresas = df[["CNPJ_CIA", "DENOM_CIA"]].drop_duplicates(subset="CNPJ_CIA")
    return empresas.sort_values("DENOM_CIA").reset_index(drop=True)


def baixar_cadastro(forcar: bool = False) -> Path:
    """
    Baixa o cadastro geral de companhias abertas da CVM (setor, situação,
    tipo de mercado, categoria de registro, controle acionário, auditor
    etc.) — um único arquivo (~1,5 MB) com todas as empresas, sem separação
    por ano. Diferente dos ZIPs de ITR/DFP (que nunca mudam depois de
    publicados), este arquivo é atualizado pela CVM sempre que algo
    cadastral muda — por isso o cache expira em 7 dias, não é permanente.
    """
    caminho = RAW_DIR / "cad_cia_aberta.csv"
    if caminho.exists() and not forcar:
        idade_dias = (time.time() - caminho.stat().st_mtime) / 86400
        if idade_dias < 7:
            print(f"📁 Usando cache: {caminho}")
            return caminho

    url = f"{CVM_BASE_URL_CAD}/cad_cia_aberta.csv"
    print(f"📥 Baixando {url} ...")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    caminho.write_bytes(resp.content)
    print(f"✅ Salvo em {caminho}")
    return caminho


def buscar_dados_cadastrais(cnpj: str) -> dict:
    """
    Busca os dados cadastrais (não financeiros) de uma empresa: setor de
    atividade, situação, tipo de mercado, categoria de registro, controle
    acionário, auditor, datas de registro/constituição, endereço da sede etc.
    """
    caminho = baixar_cadastro()
    df = pd.read_csv(caminho, sep=";", encoding="latin1", dtype=str)
    df["_CNPJ_NORM"] = df["CNPJ_CIA"].apply(_normalizar_cnpj)

    linha = df[df["_CNPJ_NORM"] == _normalizar_cnpj(cnpj)]
    if linha.empty:
        print(f"⚠️ CNPJ {cnpj} não encontrado no cadastro geral")
        return {}
    return linha.iloc[0].drop("_CNPJ_NORM").to_dict()


def _baixar_zip_fca(ano: int, forcar: bool = False) -> Path:
    caminho = RAW_DIR / f"fca_cia_aberta_{ano}.zip"
    if caminho.exists() and not forcar:
        print(f"📁 Usando cache: {caminho}")
        return caminho

    url = f"{CVM_BASE_URL_FCA}/fca_cia_aberta_{ano}.zip"
    print(f"📥 Baixando {url} ...")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    caminho.write_bytes(resp.content)
    print(f"✅ Salvo em {caminho}")
    return caminho


def buscar_dados_fca(cnpj: str) -> dict:
    """
    Busca dados do Formulário Cadastral (FCA), que complementa o cadastro
    geral com: descrição do negócio em texto livre, ticker(s) de negociação
    na B3, segmento de listagem (Novo Mercado, Nível 1/2, Tradicional), site
    institucional e nome empresarial anterior.

    Tenta o ano corrente e cai pro anterior se a CVM ainda não tiver
    publicado o FCA daquele ano pra essa empresa.
    """
    cnpj_alvo = _normalizar_cnpj(cnpj)
    ano_atual = date.today().year

    for ano in (ano_atual, ano_atual - 1):
        try:
            caminho_zip = _baixar_zip_fca(ano)
        except requests.exceptions.HTTPError:
            continue

        resultado = {}
        with zipfile.ZipFile(caminho_zip) as z:
            nome_geral = f"fca_cia_aberta_geral_{ano}.csv"
            if nome_geral in z.namelist():
                with z.open(nome_geral) as f:
                    df = pd.read_csv(f, sep=";", encoding="latin1", dtype=str)
                df["_CNPJ_NORM"] = df["CNPJ_Companhia"].apply(_normalizar_cnpj)
                linhas = df[df["_CNPJ_NORM"] == cnpj_alvo].sort_values("Data_Referencia")
                if not linhas.empty:
                    ultima = linhas.iloc[-1]
                    resultado["Descricao_Atividade"] = ultima.get("Descricao_Atividade")
                    resultado["Pagina_Web"] = ultima.get("Pagina_Web")
                    resultado["Nome_Empresarial_Anterior"] = ultima.get("Nome_Empresarial_Anterior")

            nome_vm = f"fca_cia_aberta_valor_mobiliario_{ano}.csv"
            if nome_vm in z.namelist():
                with z.open(nome_vm) as f:
                    df_vm = pd.read_csv(f, sep=";", encoding="latin1", dtype=str)
                df_vm["_CNPJ_NORM"] = df_vm["CNPJ_Companhia"].apply(_normalizar_cnpj)
                linhas_vm = df_vm[(df_vm["_CNPJ_NORM"] == cnpj_alvo) & (df_vm["Mercado"] == "Bolsa")]
                if not linhas_vm.empty:
                    tickers = sorted(linhas_vm["Codigo_Negociacao"].dropna().unique())
                    segmentos = sorted(linhas_vm["Segmento"].dropna().unique())
                    resultado["Codigo_Negociacao"] = ", ".join(tickers)
                    resultado["Segmento"] = ", ".join(segmentos)

        if resultado:
            return resultado

    print(f"⚠️ Dados do FCA não encontrados para CNPJ {cnpj}")
    return {}


def _rotulo_periodo(row) -> str:
    """Monta um rótulo de período a partir de DT_INI_EXERC/DT_FIM_EXERC (quando existir)."""
    fim = row.get("DT_FIM_EXERC", "")
    inicio = row.get("DT_INI_EXERC", None)
    if inicio and isinstance(inicio, str) and inicio == inicio:  # não é NaN
        return f"{inicio} a {fim}"
    return str(fim)


def _pivotar_padrao(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pivota uma demonstração no formato CVM (linhas = conta x período) para
    o formato de planilha (linhas = conta, colunas = período).

    Usa DT_INI_EXERC + DT_FIM_EXERC como chave de período (em vez de
    ULTIMO/PENÚLTIMO) porque isso distingui corretamente trimestre "no
    período de 3 meses" de "acumulado no ano", que aparecem lado a lado
    no mesmo envio de ITR.
    """
    if df.empty:
        return df

    df = df.copy()
    df["PERIODO"] = df.apply(_rotulo_periodo, axis=1)

    tabela = df.pivot_table(
        index=["CD_CONTA", "DS_CONTA"],
        columns="PERIODO",
        values="VL_CONTA",
        aggfunc="first",
    )
    # Ordena as linhas pelo código da conta (mantém a hierarquia contábil original)
    tabela = tabela.sort_index(level="CD_CONTA")
    # Ordena as colunas por data final do período
    tabela = tabela.reindex(sorted(tabela.columns, key=lambda c: c.split(" a ")[-1]), axis=1)
    return tabela


def _pivotar_dmpl(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pivota a DMPL, que tem uma dimensão a mais (COLUNA_DF = conta do patrimônio
    líquido, ex: Capital Social, Reservas, Lucros Acumulados).
    Resultado: colunas em MultiIndex (COLUNA_DF, período).
    """
    if df.empty:
        return df

    df = df.copy()
    df["PERIODO"] = df.apply(_rotulo_periodo, axis=1)

    tabela = df.pivot_table(
        index=["CD_CONTA", "DS_CONTA"],
        columns=["COLUNA_DF", "PERIODO"],
        values="VL_CONTA",
        aggfunc="first",
    )
    tabela = tabela.sort_index(level="CD_CONTA")
    return tabela


def _normalizar_descricoes(df: pd.DataFrame) -> pd.DataFrame:
    """
    O texto de DS_CONTA pode variar ligeiramente entre anos mesmo quando
    CD_CONTA continua o mesmo (ex: "Custo com Pesquisa..." em 2015 vira
    "Custos com pesquisa..." em 2024). Sem normalizar isso, cada variação de
    texto viraria uma linha nova ao combinar vários anos. Aqui, todo CD_CONTA
    passa a usar a descrição do envio mais recente (maior DT_REFER).
    """
    if df.empty or "DT_REFER" not in df.columns:
        return df

    descricao_atual = (
        df.sort_values("DT_REFER")
        .drop_duplicates(subset="CD_CONTA", keep="last")
        .set_index("CD_CONTA")["DS_CONTA"]
    )
    df = df.copy()
    df["DS_CONTA"] = df["CD_CONTA"].map(descricao_atual)
    return df


_DURACOES_VALIDAS_DIAS = [90, 91, 92, 181, 182, 183, 273, 274, 275, 365, 366]  # ~3, 6, 9 e 12 meses


def _validar_periodos(bruto: pd.DataFrame, sigla: str) -> pd.DataFrame:
    """
    Confere se cada linha realmente pertence ao período que vai virar rótulo
    de coluna, ANTES de pivotar — protege contra inconsistência nos dados
    abertos da CVM (ex: DT_FIM_EXERC que não cai em fim de trimestre, ou
    duração de período fora do esperado). Linhas reprovadas são descartadas
    com aviso, em vez de silenciosamente distorcer uma coluna do Excel.
    """
    if bruto.empty:
        return bruto

    dt_fim = pd.to_datetime(bruto["DT_FIM_EXERC"])
    # A Camil (exercício mar-fev) informa o fim do ano fiscal como 28/02 mesmo em ano
    # bissexto, enquanto o balanço vem em 29/02: normaliza para o último dia do mês.
    fev_bissexto = (dt_fim.dt.month == 2) & (dt_fim.dt.day == 28) & dt_fim.dt.is_leap_year
    if fev_bissexto.any():
        bruto = bruto.copy()
        dt_fim = dt_fim.where(~fev_bissexto, dt_fim + pd.offsets.MonthEnd(0))
        bruto["DT_FIM_EXERC"] = dt_fim.dt.strftime("%Y-%m-%d")
    # Fim de mês, não necessariamente mar/jun/set/dez: há exercícios abr-mar (São Martinho)
    # e mar-fev (Camil). A duração (3/6/9/12 meses) continua sendo checada abaixo.
    fim_valido = dt_fim.dt.is_month_end

    duracao_valida = pd.Series(True, index=bruto.index)
    if "DT_INI_EXERC" in bruto.columns:
        dt_ini = pd.to_datetime(bruto["DT_INI_EXERC"])
        dias = (dt_fim - dt_ini).dt.days
        duracao_valida = dias.apply(lambda d: any(abs(d - esperado) <= 3 for esperado in _DURACOES_VALIDAS_DIAS))

    # Cruza com DT_REFER (a data do próprio envio): o ITR/DFP só reporta o
    # período corrente e o comparativo do ano anterior, nunca mais que isso.
    # Se DT_FIM_EXERC cair fora dessa janela, o ano bateu errado — é
    # exatamente o cenário "1T de 2018 rotulado como 1T de 2019/2020".
    ano_referencia = pd.to_datetime(bruto["DT_REFER"]).dt.year
    ano_condiz_com_envio = (dt_fim.dt.year >= ano_referencia - 1) & (dt_fim.dt.year <= ano_referencia)

    valida = fim_valido & duracao_valida & ano_condiz_com_envio
    if not valida.all():
        invalidas = bruto[~valida]
        colunas = [c for c in ["DT_REFER", "VERSAO", "DT_INI_EXERC", "DT_FIM_EXERC", "CD_CONTA", "DS_CONTA"]
                   if c in invalidas.columns]
        print(f"\n⚠️ {sigla}: {len(invalidas)} linha(s) com período inconsistente — descartadas:")
        print(invalidas[colunas].drop_duplicates().to_string(index=False))

    return bruto[valida]


def _avisar_conflitos_de_valor(bruto: pd.DataFrame, chave: list, sigla: str) -> None:
    """
    Avisa se duas linhas do MESMO documento (mesmo DT_REFER + VERSAO) trazem
    valores diferentes para a mesma conta/período — isso sim indicaria uma
    inconsistência real dentro de um único envio à CVM.

    Importante: VERSAO é numerado por DOCUMENTO, não por período — o mesmo
    VERSAO=1 aparece em documentos completamente diferentes (ex: o filing de
    2018-03-31 e o comparativo trazido pelo filing de 2019-03-31), então NÃo
    dá pra comparar VERSAO entre DT_REFER diferentes. Quando o valor de um
    mesmo período muda de um filing pro outro, isso é reapresentação/
    reclassificação normal — resolvida em buscar_itr() mantendo sempre o
    filing (DT_REFER) mais recente, não tratada aqui como erro.
    """
    chave_do_documento = chave + ["DT_REFER", "VERSAO"]
    agrupado = bruto.groupby(chave_do_documento)["VL_CONTA"].nunique()
    conflitantes = agrupado[agrupado > 1]
    if conflitantes.empty:
        return
    print(f"\n⚠️ {sigla}: {len(conflitantes)} conta(s) com valores DIVERGENTES dentro do MESMO documento "
          f"(DT_REFER+VERSAO) — inconsistência real na base da CVM:")
    print(conflitantes.reset_index().to_string(index=False))


# Contas de nível 3+ da DFC e 4+ do Balanço não são padronizadas pela CVM: cada empresa
# numera as suas e pode reaproveitar um código para outro item em outro ano (a Klabin usou
# 6.03.05 para "Dividendos pagos" até 2022 e para outra linha depois).
_CONTAS_PADRAO_DFC = {"6.01.01", "6.01.02", "6.01.03", "6.05.01", "6.05.02"}
_PALAVRAS_VAZIAS = {"de", "da", "do", "das", "dos", "e", "a", "o", "as", "os", "em", "no", "na", "nos", "nas",
                    "com", "para", "por", "sobre", "s", "sob", "ao", "aos"}


def _conta_propria_da_empresa(cd: str, sigla: str) -> bool:
    nivel = cd.count(".") + 1
    if sigla == "DFC_MI":
        return nivel >= 3 and cd not in _CONTAS_PADRAO_DFC
    if sigla in ("BPA", "BPP"):
        return nivel >= 4
    return False


def _manter_ultimo_envio_por_periodo(bruto: pd.DataFrame) -> pd.DataFrame:
    """
    Para cada período, fica só o envio mais recente que o contém (todas as contas do
    mesmo documento). Evita juntar, no mesmo período, a numeração antiga e a nova de
    uma empresa que reorganizou as contas próprias.
    """
    periodo = bruto["DT_FIM_EXERC"].astype(str)
    if "DT_INI_EXERC" in bruto.columns:
        periodo = bruto["DT_INI_EXERC"].astype(str) + "|" + periodo
    envio = bruto["DT_REFER"].astype(str) + "|" + bruto["VERSAO"].astype(str).str.zfill(4)
    return bruto[envio == envio.groupby(periodo).transform("max")]


def _tokens(texto: str) -> set:
    import unicodedata
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    palavras = re.sub(r"[^a-z0-9]+", " ", t).split()
    # radical de 5 letras: junta plural e flexões ("depreciações"/"depreciação", "provisão"/"provisões");
    # "pagos"/"pagamento" e "recebidos"/"recebimento" viram o mesmo radical
    radicais = set()
    for p in palavras:
        if p in _PALAVRAS_VAZIAS:
            continue
        radicais.add("pag" if p.startswith("pag") else "receb" if p.startswith("receb") else p[:5])
    return radicais


# Palavras que mudam o sentido da linha: se aparecem num nome e não no outro, não é a mesma conta
_RADICAIS_DE_SENTIDO = {"resga", "aquis", "venda", "alien", "capta", "amort", "pag", "receb", "baixa", "aumen",
                        "reduc", "emiss", "recom", "integ", "entra", "saida", "exaus", "depre", "valor", "justo"}


def _mesma_conta(a: str, b: str) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb or (ta ^ tb) & _RADICAIS_DE_SENTIDO:
        return False
    return len(ta & tb) / len(ta | tb) >= 0.5


def _separar_contas_reaproveitadas(bruto: pd.DataFrame, sigla: str) -> pd.DataFrame:
    """
    Quando o mesmo código próprio da empresa aparece com descrições de itens diferentes
    em anos diferentes, cada significado vira uma linha separada ("6.03.05" para o atual,
    "6.03.05~1" para o anterior...). Variações só de texto ("Custo com"/"Custos com")
    continuam juntas.
    """
    novos = {}
    for cd, grupo in bruto.groupby("CD_CONTA"):
        if not _conta_propria_da_empresa(cd, sigla):
            continue
        recencia = grupo.groupby("DS_CONTA")["DT_REFER"].max().sort_values(ascending=False)
        if len(recencia) < 2:
            continue
        representantes = []  # descrição mais recente de cada significado
        for desc in recencia.index:
            k = next((i for i, rep in enumerate(representantes) if _mesma_conta(desc, rep)), None)
            if k is None:
                representantes.append(desc)
                k = len(representantes) - 1
            if k:
                novos[(cd, desc)] = f"{cd}~{k}"
    bruto = bruto.copy()
    if novos:
        chave = list(zip(bruto["CD_CONTA"], bruto["DS_CONTA"]))
        bruto["CD_CONTA"] = [novos.get(c, c[0]) for c in chave]
    return _juntar_mesmo_item_com_codigos_diferentes(bruto, sigla)


def _juntar_mesmo_item_com_codigos_diferentes(bruto: pd.DataFrame, sigla: str) -> pd.DataFrame:
    """
    O inverso: o mesmo item que mudou de código entre anos (WEG: "Imobilizado" em 6.02.01
    e depois em 6.02.02) vira uma linha só, no código mais recente — desde que as duas
    linhas nunca apareçam no mesmo período (aí seriam itens distintos com nome parecido).
    """
    periodo = bruto["DT_FIM_EXERC"].astype(str)
    if "DT_INI_EXERC" in bruto.columns:
        periodo = bruto["DT_INI_EXERC"].astype(str) + "|" + periodo
    info = (bruto.assign(_PER=periodo).groupby("CD_CONTA")
            .agg(desc=("DS_CONTA", lambda d: d.loc[bruto.loc[d.index, "DT_REFER"].idxmax()]),
                 recente=("DT_REFER", "max"), periodos=("_PER", lambda x: set(x))))
    destino = {}
    for pai, grupo in info.groupby(lambda cd: cd.split("~")[0].rsplit(".", 1)[0]):
        candidatos = [cd for cd in grupo.sort_values("recente", ascending=False).index
                      if _conta_propria_da_empresa(cd.split("~")[0], sigla)]
        grupos = []  # [código representante, descrição, períodos ocupados]
        for cd in candidatos:
            desc, pers = grupo.at[cd, "desc"], grupo.at[cd, "periodos"]
            alvo = next((g for g in grupos if not (g[2] & pers) and _mesma_conta(desc, g[1])), None)
            if alvo is None:
                grupos.append([cd, desc, set(pers)])
            else:
                destino[cd] = alvo[0]
                alvo[2] |= pers
    if destino:
        bruto["CD_CONTA"] = bruto["CD_CONTA"].map(lambda cd: destino.get(cd, cd))
    return bruto


_ESCALAS = {"MIL": 1000, "UNIDADE": 1}


def _unificar_escala(bruto: pd.DataFrame):
    """
    Algumas empresas mudam a escala entre envios (milhares num ano, reais no outro — ex.:
    Pague Menos). Converte tudo para a escala do envio mais recente, para as colunas da
    planilha ficarem na mesma unidade. Retorna (DataFrame, escala usada).
    """
    if "ESCALA_MOEDA" not in bruto.columns or bruto["ESCALA_MOEDA"].dropna().empty:
        return bruto, None
    recente = bruto.loc[bruto["DT_REFER"].idxmax(), "ESCALA_MOEDA"]
    if bruto["ESCALA_MOEDA"].nunique() > 1 and recente in _ESCALAS:
        bruto = bruto.copy()
        fator = bruto["ESCALA_MOEDA"].map(_ESCALAS).fillna(_ESCALAS[recente]) / _ESCALAS[recente]
        bruto["VL_CONTA"] = bruto["VL_CONTA"] * fator
        bruto["ESCALA_MOEDA"] = recente
    return bruto, recente


def _series_por_descricao(bruto: pd.DataFrame) -> dict:
    """
    D&A, capex e dividendos pagos por trimestre isolado, somando as linhas cuja descrição
    casa em CADA envio (o mesmo cálculo do site). Imune a códigos renumerados ou
    renomeados entre envios. Chaves: data de fim (AAAA-MM-DD).
    """
    from src.indicadores import EXCLUI_CAPEX, EXCLUI_DA, PADRAO_CAPEX, PADRAO_DA
    from src.padrao_visual import isolar_trimestres

    padrao_div = re.compile(r"dividend|juros sobre (?:o )?capital|\bjcp\b", re.I)
    regras = {"da": ("6.01.01", PADRAO_DA, EXCLUI_DA), "capex": ("6.02", PADRAO_CAPEX, EXCLUI_CAPEX),
              "dividendos": ("6.03", padrao_div, re.compile(r"receb", re.I))}
    if "DT_INI_EXERC" not in bruto.columns:
        return {}
    periodo = bruto["DT_INI_EXERC"].astype(str) + " a " + bruto["DT_FIM_EXERC"].astype(str)
    todos = sorted(periodo.unique())
    saida = {"linhas": {}}
    for nome, (prefixo, padrao, exclui) in regras.items():
        nivel = prefixo.count(".") + 1
        cd, ds = bruto["CD_CONTA"], bruto["DS_CONTA"].astype(str)
        casa = (cd.str.startswith(prefixo + ".") & (cd.str.count(r"\.") == nivel)
                & ds.str.contains(padrao) & ~ds.str.contains(exclui))
        soma = bruto.loc[casa, "VL_CONTA"].groupby(periodo[casa]).sum().reindex(todos, fill_value=0.0)
        isolada = isolar_trimestres(pd.DataFrame([soma]), preferir_derivado=True).iloc[0]
        saida[nome] = {c.split(" a ")[1]: float(v) for c, v in isolada.items()}
        saida["linhas"][nome] = sorted(ds[casa].str.strip().unique())
    return saida


def buscar_itr(cnpj: str, anos, tipo: str = "con") -> dict:
    """
    Busca as 5 demonstrações do ITR (BPA, BPP, DRE, DFC_MI, DMPL) para uma
    empresa em um ou mais anos, já combinadas e pivotadas em formato de planilha.

    Cada ZIP anual da CVM já traz, junto com o período corrente, os períodos
    comparativos do ano anterior (PENÚLTIMO). Ao juntar vários anos, essas
    comparações se sobrepõem — por isso os dados brutos de todos os anos são
    concatenados e deduplicados por período ANTES de pivotar, em vez de
    pivotar ano a ano e depois juntar (o que geraria colunas repetidas).

    Args:
        cnpj:  CNPJ da empresa (com ou sem formatação)
        anos:  um ano (int) ou uma lista/range de anos, ex: range(2015, 2025)
        tipo:  "con" (consolidado, default) ou "ind" (individual).
               Empresas sem controladas só têm dados em "ind".
    Returns:
        dict {"Balanço Patrimonial Ativo": df, "Demonstração do Resultado": df, ...}
    """
    if isinstance(anos, int):
        anos = [anos]

    resultado = {}
    for sigla, titulo in DEMONSTRACOES_ITR.items():
        blocos = []
        for ano in anos:
            print(f"\n🔎 {titulo} ({sigla}_{tipo}, {ano})")
            bruto = _ler_demonstracao(ano, sigla, tipo, cnpj)

            if bruto.empty and tipo == "con":
                print("   ↪ sem consolidado, tentando individual (ind)...")
                bruto = _ler_demonstracao(ano, sigla, "ind", cnpj)

            if not bruto.empty:
                blocos.append(bruto)

            # O ITR não cobre o ano completo (só 1T/2T/3T). Para DRE e DFC,
            # busca também o DFP (anual) do mesmo ano — dá o acumulado
            # Jan-Dez, usado depois para calcular o 4º trimestre isolado
            # (DRE) e para completar a série acumulada (DFC).
            if sigla in ("DRE", "DFC_MI"):
                bruto_dfp = _ler_demonstracao(ano, sigla, tipo, cnpj, fonte="DFP")
                if bruto_dfp.empty and tipo == "con":
                    bruto_dfp = _ler_demonstracao(ano, sigla, "ind", cnpj, fonte="DFP")
                if not bruto_dfp.empty:
                    blocos.append(bruto_dfp)

        bruto_total = pd.concat(blocos, ignore_index=True) if blocos else pd.DataFrame()

        escala = None
        por_descricao = None
        if not bruto_total.empty:
            bruto_total, escala = _unificar_escala(bruto_total)
            bruto_total = _validar_periodos(bruto_total, sigla)
            if sigla in ("BPA", "BPP", "DFC_MI"):
                bruto_total = _manter_ultimo_envio_por_periodo(bruto_total)
                if sigla == "DFC_MI":
                    por_descricao = _series_por_descricao(bruto_total)
                bruto_total = _separar_contas_reaproveitadas(bruto_total, sigla)
            bruto_total = _normalizar_descricoes(bruto_total)

            chave = ["CD_CONTA", "DT_FIM_EXERC"]
            if "DT_INI_EXERC" in bruto_total.columns:
                chave.append("DT_INI_EXERC")
            if sigla == "DMPL":
                chave.append("COLUNA_DF")

            _avisar_conflitos_de_valor(bruto_total, chave, sigla)
            # Mantém o dado do envio (DT_REFER) mais recente para cada período,
            # com VERSAO como desempate dentro do mesmo envio. Ordenar só por
            # VERSAO seria errado: esse número é por DOCUMENTO, não por
            # período — o mesmo período pode aparecer em vários DT_REFER
            # diferentes (como comparativo), cada um com sua própria contagem
            # de versão, e o envio mais recente é o que vale (reapresentação).
            bruto_total = bruto_total.sort_values(["DT_REFER", "VERSAO"]).drop_duplicates(subset=chave, keep="last")

        if sigla == "DMPL":
            pivotada = _pivotar_dmpl(bruto_total)
        else:
            pivotada = _pivotar_padrao(bruto_total)

        pivotada.attrs["escala"] = escala
        if por_descricao is not None:
            pivotada.attrs["por_descricao"] = por_descricao
        resultado[titulo] = pivotada

    return resultado


_PADRAO_ARRENDAMENTO = re.compile(r"arrendament|leasing|direito de uso", re.I)
_EXCLUI_ARRENDAMENTO = re.compile(r"receb", re.I)
_CONTAS_DIVIDA = ("2.01.04", "2.02.01")


def arrendamentos_no_passivo(bpp: pd.DataFrame) -> pd.DataFrame:
    """
    Passivos de arrendamento (IFRS 16) por data, identificados pela descrição em
    qualquer nível do Passivo (circulante e não circulante). Separa o que a empresa
    lançou DENTRO de empréstimos e financiamentos (2.01.04/2.02.01, já somado à dívida)
    do que está FORA (em outras obrigações). Em cada ramo conta só a linha mais alta que
    casa, para não somar pai e filho.
    Retorna DataFrame com colunas "dentro" e "fora", indexado pela data (como no BP).
    """
    if bpp is None or bpp.empty:
        return pd.DataFrame()
    cods = bpp.index.get_level_values("CD_CONTA")
    descs = bpp.index.get_level_values("DS_CONTA")
    casam = [
        i for i, (cd, desc) in enumerate(zip(cods, descs))
        if cd.startswith(("2.01.", "2.02.")) and cd.count(".") >= 2
        and _PADRAO_ARRENDAMENTO.search(str(desc)) and not _EXCLUI_ARRENDAMENTO.search(str(desc))
    ]
    base = {cods[i].split("~")[0] for i in casam}
    topo = [i for i in casam
            if not any(cods[i].split("~")[0].startswith(outro + ".") for outro in base if outro != cods[i].split("~")[0])]
    dentro = [i for i in topo if cods[i].startswith(_CONTAS_DIVIDA)]
    fora = [i for i in topo if not cods[i].startswith(_CONTAS_DIVIDA)]
    soma = lambda idx: bpp.iloc[idx].sum() if idx else pd.Series(0.0, index=bpp.columns)
    return pd.DataFrame({"dentro": soma(dentro), "fora": soma(fora)}).fillna(0.0)


def filtrar_nivel(tabela: pd.DataFrame, nivel_maximo: int) -> pd.DataFrame:
    """
    Mantém só as contas até um nível hierárquico (nível = nº de pontos em
    CD_CONTA + 1). Ex: nivel_maximo=3 mantém até "1.01.01" e descarta "1.01.01.01".
    """
    if tabela.empty:
        return tabela
    niveis = tabela.index.get_level_values("CD_CONTA").str.count(r"\.") + 1
    return tabela[niveis <= nivel_maximo]


def montar_documento_padrao(
    demonstracoes: dict,
    ano_inicio: int = None,
    nivel_dre: int = 3,
    nivel_bp: int = 3,
    nivel_dfc: int = 4,
) -> list:
    """
    Monta a lista de blocos do documento padrão do projeto, na ordem definida:
    1) DRE — até nível 3, só trimestre isolado (sem as colunas acumuladas,
       que duplicariam a data final da coluna de trimestre), sem as contas
       de EPS/atribuição societária, datas em dd/mm/aa
    2) Balanço Patrimonial — Ativo + Passivo juntos, até nível 3, datas em dd/mm/aa
    3) DFC método indireto — até nível 4, também isolado por trimestre (a CVM só
       publica acumulado; cada trimestre é obtido subtraindo o acumulado
       anterior — ver padrao_visual.isolar_trimestres), datas em dd/mm/aa

    Os três blocos são alinhados para ter exatamente os MESMOS períodos (ver
    padrao_visual.alinhar_periodos) — o Balanço só compara com o fechamento
    anual anterior, não com o mesmo trimestre do ano passado como DRE/DFC,
    então sem esse alinhamento os três sairiam com números de colunas diferentes.

    Cada linha recebe uma classificação (total/subtotal/detalhe) usada pela
    exportação para aplicar as cores do padrão visual do projeto.

    Args:
        demonstracoes: saída de buscar_itr()
        ano_inicio: se informado, descarta qualquer período anterior a esse
                    ano (evita "vazamento" do comparativo do ano anterior ao
                    pedido, que a CVM inclui no primeiro ano da faixa)
        nivel_dre, nivel_bp, nivel_dfc: profundidade máxima de cada bloco
    Returns:
        lista de tuplas (titulo_do_bloco, DataFrame) — DataFrames já prontos
        para exportação (sem CD_CONTA, com df.attrs["estilos"] preenchido)
    """
    from src.padrao_visual import (
        EXCLUSOES_DRE, CLASSIFICACAO_DRE, CLASSIFICACAO_BP, CLASSIFICACAO_DFC,
        remover_contas, isolar_trimestres,
        filtrar_data_minima, alinhar_periodos, preparar_bloco,
    )

    data_minima = f"{ano_inicio}-01-01" if ano_inicio else None

    dre = filtrar_nivel(demonstracoes.get("Demonstração do Resultado", pd.DataFrame()), nivel_dre)
    dre = remover_contas(dre, EXCLUSOES_DRE)
    dre = isolar_trimestres(dre)  # trimestre isolado, com o 4T derivado (DFP anual − 9M)

    bpa = filtrar_nivel(demonstracoes.get("Balanço Patrimonial Ativo", pd.DataFrame()), nivel_bp)
    bpp = filtrar_nivel(demonstracoes.get("Balanço Patrimonial Passivo", pd.DataFrame()), nivel_bp)
    balanco = pd.concat([bpa, bpp]) if not bpa.empty or not bpp.empty else pd.DataFrame()

    dfc = filtrar_nivel(
        demonstracoes.get("Demonstração do Fluxo de Caixa (Método Indireto)", pd.DataFrame()), nivel_dfc
    )
    dfc = isolar_trimestres(dfc, preferir_derivado=True)  # a CVM só publica acumulado; isola cada trimestre por subtração

    if data_minima:
        dre = filtrar_data_minima(dre, data_minima)
        balanco = filtrar_data_minima(balanco, data_minima)
        dfc = filtrar_data_minima(dfc, data_minima)

    dre, balanco, dfc = alinhar_periodos(dre, balanco, dfc)

    # Contas próprias da empresa (DFC nível 3+) sem valor em nenhum período exibido saem:
    # depois de separar/juntar códigos reaproveitados, sobram linhas vazias que só poluem
    def _sem_linhas_proprias_vazias(tabela, sigla):
        if tabela.empty:
            return tabela
        cods = tabela.index.get_level_values("CD_CONTA")
        propria = [_conta_propria_da_empresa(c.split("~")[0], sigla) for c in cods]
        vazia = tabela.fillna(0).eq(0).all(axis=1)
        return tabela[~(pd.Series(propria, index=tabela.index) & vazia)]

    dfc = _sem_linhas_proprias_vazias(dfc, "DFC_MI")

    arrendamentos = arrendamentos_no_passivo(demonstracoes.get("Balanço Patrimonial Passivo", pd.DataFrame()))

    dre = preparar_bloco(dre, CLASSIFICACAO_DRE, modo_data="fim")
    colunas_balanco = list(balanco.columns)
    balanco = preparar_bloco(balanco, CLASSIFICACAO_BP, modo_data="unica")
    # Arrendamentos (IFRS 16) não aparecem no nível 3 do Balanço: seguem junto do bloco,
    # por data, para a aba de indicadores e o site calcularem a dívida com e sem eles
    balanco.attrs["arrendamentos"] = {
        rotulo: {k: float(arrendamentos[k].get(c, 0.0)) for k in ("dentro", "fora")}
        for c, rotulo in zip(colunas_balanco, balanco.columns)
    } if not arrendamentos.empty else {}
    colunas_dfc = list(dfc.columns)
    dfc = preparar_bloco(dfc, CLASSIFICACAO_DFC, modo_data="fim")
    # Séries calculadas por descrição (D&A, capex, dividendos), por rótulo de coluna
    por_desc = demonstracoes.get("Demonstração do Fluxo de Caixa (Método Indireto)", pd.DataFrame()).attrs.get("por_descricao") or {}
    if por_desc:
        fim = {c: c.split(" a ")[-1] for c in colunas_dfc}
        dfc.attrs["por_descricao"] = {
            nome: {rotulo: valores.get(fim[c], 0.0) for c, rotulo in zip(colunas_dfc, dfc.columns)}
            for nome, valores in por_desc.items() if nome != "linhas"
        }
        dfc.attrs["por_descricao_linhas"] = por_desc.get("linhas", {})
    balanco.attrs["escala"] = demonstracoes.get("Balanço Patrimonial Passivo", pd.DataFrame()).attrs.get("escala")

    return [
        ("DRE", dre),
        ("Balanço Patrimonial", balanco),
        ("DFC (Método Indireto)", dfc),
    ]
