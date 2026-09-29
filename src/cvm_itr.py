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


_FINS_DE_TRIMESTRE_VALIDOS = {(3, 31), (6, 30), (9, 30), (12, 31)}
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
    fim_valido = dt_fim.apply(lambda d: (d.month, d.day) in _FINS_DE_TRIMESTRE_VALIDOS)

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

        if not bruto_total.empty:
            bruto_total = _normalizar_descricoes(bruto_total)
            bruto_total = _validar_periodos(bruto_total, sigla)

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

        resultado[titulo] = pivotada

    return resultado


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
       anterior — ver padrao_visual.isolar_dfc), datas em dd/mm/aa

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
        remover_contas, calcular_quarto_trimestre, isolar_dfc, somente_trimestre_isolado,
        filtrar_data_minima, alinhar_periodos, preparar_bloco,
    )

    data_minima = f"{ano_inicio}-01-01" if ano_inicio else None

    dre = filtrar_nivel(demonstracoes.get("Demonstração do Resultado", pd.DataFrame()), nivel_dre)
    dre = remover_contas(dre, EXCLUSOES_DRE)
    dre = calcular_quarto_trimestre(dre)  # deriva o 4T (DFP anual - ITR 9m), antes de isolar
    dre = somente_trimestre_isolado(dre)

    bpa = filtrar_nivel(demonstracoes.get("Balanço Patrimonial Ativo", pd.DataFrame()), nivel_bp)
    bpp = filtrar_nivel(demonstracoes.get("Balanço Patrimonial Passivo", pd.DataFrame()), nivel_bp)
    balanco = pd.concat([bpa, bpp]) if not bpa.empty or not bpp.empty else pd.DataFrame()

    dfc = filtrar_nivel(
        demonstracoes.get("Demonstração do Fluxo de Caixa (Método Indireto)", pd.DataFrame()), nivel_dfc
    )
    dfc = isolar_dfc(dfc)  # a CVM só publica acumulado; isola cada trimestre por subtração

    if data_minima:
        dre = filtrar_data_minima(dre, data_minima)
        balanco = filtrar_data_minima(balanco, data_minima)
        dfc = filtrar_data_minima(dfc, data_minima)

    dre, balanco, dfc = alinhar_periodos(dre, balanco, dfc)

    dre = preparar_bloco(dre, CLASSIFICACAO_DRE, modo_data="fim")
    balanco = preparar_bloco(balanco, CLASSIFICACAO_BP, modo_data="unica")
    dfc = preparar_bloco(dfc, CLASSIFICACAO_DFC, modo_data="fim")

    return [
        ("DRE", dre),
        ("Balanço Patrimonial", balanco),
        ("DFC (Método Indireto)", dfc),
    ]
