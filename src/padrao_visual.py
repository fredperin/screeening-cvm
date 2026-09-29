"""
padrao_visual.py — Regras do "documento padrão" do projeto: quais contas
excluir, como classificar cada conta (total/subtotal/detalhe) para a
formatação visual, e como formatar datas/números.

Os códigos de conta (CD_CONTA) são padronizados pela CVM para todas as
empresas NÃO financeiras (confirmado testando 5 empresas de setores
diferentes), por isso essas regras funcionam igual para qualquer empresa
não financeira, sem precisar de ajuste por empresa.
"""

import re
import pandas as pd

# Contas que aparecem no ITR mas não têm utilidade para acompanhamento
# (detalhamentos de EPS e quebras de atribuição societária que não agregam
# à leitura do resultado).
EXCLUSOES_DRE = {
    "3.10.01",  # Lucro/Prejuízo Líquido das Operações Descontinuadas
    "3.10.02",  # Ganhos/Perdas Líquidas sobre Ativos de Operações Descontinuadas
    "3.11.01",  # Atribuído a Sócios da Empresa Controladora
    "3.11.02",  # Atribuído a Sócios Não Controladores
    "3.99",     # Lucro por Ação
    "3.99.01",  # Lucro Básico por Ação
    "3.99.02",  # Lucro Diluído por Ação
}

# "total"    = resultado/saldo-chave, destaque máximo (verde)
# "subtotal" = agregação estrutural intermediária (cinza)
# (tudo que não estiver aqui é "detalhe" — sem destaque)
CLASSIFICACAO_DRE = {
    "3.03": "total",  # Resultado Bruto
    "3.05": "total",  # Resultado Antes do Resultado Financeiro e dos Tributos
    "3.07": "total",  # Resultado Antes dos Tributos sobre o Lucro
    "3.11": "total",  # Lucro/Prejuízo Consolidado do Período
}

CLASSIFICACAO_BP = {
    "1": "total", "2": "total", "2.03": "total",         # Ativo/Passivo Total, Patrimônio Líquido
    "1.01": "subtotal", "1.02": "subtotal",               # Ativo Circulante/Não Circulante
    "2.01": "subtotal", "2.02": "subtotal",               # Passivo Circulante/Não Circulante
}

CLASSIFICACAO_DFC = {
    "6.01": "total", "6.02": "total", "6.03": "total", "6.05": "total",
    "6.01.01": "subtotal", "6.01.02": "subtotal",
    "6.05.01": "subtotal", "6.05.02": "subtotal",
}


def remover_contas(tabela: pd.DataFrame, codigos_excluidos: set) -> pd.DataFrame:
    """Remove linhas cujo CD_CONTA está na lista de exclusão."""
    if tabela.empty:
        return tabela
    return tabela[~tabela.index.get_level_values("CD_CONTA").isin(codigos_excluidos)]


def calcular_quarto_trimestre(tabela: pd.DataFrame) -> pd.DataFrame:
    """
    A CVM não publica o 4º trimestre isolado em lugar nenhum — o ITR só cobre
    1T/2T/3T (o "acumulado até dezembro" só aparece no DFP, o relatório anual).
    Aqui ele é calculado: Q4 = Acumulado Jan-Dez (DFP) − Acumulado Jan-Set (ITR).

    Precisa rodar ANTES de somente_trimestre_isolado(), pois usa as colunas
    acumuladas (que depois são descartadas).
    """
    if tabela.empty:
        return tabela

    tabela = tabela.copy()
    novas_colunas = {}
    for rotulo in tabela.columns:
        if " a " not in rotulo:
            continue
        inicio, fim = rotulo.split(" a ")
        ano = fim[:4]
        eh_ano_completo = inicio == f"{ano}-01-01" and fim == f"{ano}-12-31"
        rotulo_9m = f"{ano}-01-01 a {ano}-09-30"
        if eh_ano_completo and rotulo_9m in tabela.columns:
            rotulo_q4 = f"{ano}-10-01 a {ano}-12-31"
            novas_colunas[rotulo_q4] = tabela[rotulo] - tabela[rotulo_9m]

    for rotulo, serie in novas_colunas.items():
        tabela[rotulo] = serie
    return tabela


def isolar_dfc(tabela: pd.DataFrame) -> pd.DataFrame:
    """
    O DFC nunca traz trimestre isolado — a CVM só publica acumulado
    (Jan-Mar, Jan-Jun, Jan-Set via ITR, Jan-Dez via DFP). Aqui cada
    trimestre é isolado por subtração do acumulado anterior:
        1T = Jan-Mar (já vem isolado, não precisa de conta)
        2T = (Jan-Jun) − (Jan-Mar)
        3T = (Jan-Set) − (Jan-Jun)
        4T = (Jan-Dez) − (Jan-Set)
    Se faltar algum acumulado do ano (ex: ano ainda em andamento, sem
    fechamento anual publicado), o(s) trimestre(s) que dependem dele
    simplesmente não são calculados — nunca gera número errado.
    """
    if tabela.empty:
        return tabela

    anos = sorted({c.split(" a ")[-1][:4] for c in tabela.columns if " a " in c})
    novas_colunas = {}

    for ano in anos:
        col_1t = f"{ano}-01-01 a {ano}-03-31"
        col_1s = f"{ano}-01-01 a {ano}-06-30"
        col_9m = f"{ano}-01-01 a {ano}-09-30"
        col_ano = f"{ano}-01-01 a {ano}-12-31"

        if col_1t in tabela.columns:
            novas_colunas[col_1t] = tabela[col_1t]
        if col_1s in tabela.columns and col_1t in tabela.columns:
            novas_colunas[f"{ano}-04-01 a {ano}-06-30"] = tabela[col_1s] - tabela[col_1t]
        if col_9m in tabela.columns and col_1s in tabela.columns:
            novas_colunas[f"{ano}-07-01 a {ano}-09-30"] = tabela[col_9m] - tabela[col_1s]
        if col_ano in tabela.columns and col_9m in tabela.columns:
            novas_colunas[f"{ano}-10-01 a {ano}-12-31"] = tabela[col_ano] - tabela[col_9m]

    return pd.DataFrame(novas_colunas, index=tabela.index)


def _data_fim(rotulo: str) -> str:
    """Extrai a data final de um rótulo de coluna, seja ele uma data única ou um intervalo."""
    return rotulo.split(" a ")[-1] if " a " in rotulo else rotulo


def filtrar_data_minima(tabela: pd.DataFrame, data_minima_iso: str) -> pd.DataFrame:
    """
    Remove colunas com data final anterior a data_minima_iso (ex: "2016-01-01").
    Usado para descartar comparativos "vazando" do ano anterior ao início
    pedido (ex: o ITR de 2016 traz comparativo com 2015).
    """
    if tabela.empty:
        return tabela
    colunas = [c for c in tabela.columns if _data_fim(c) >= data_minima_iso]
    return tabela[colunas]


def _avisar_periodos_descartados(datas_dre: set, datas_bp: set, datas_dfc: set, datas_comuns: set) -> None:
    """Avisa quando um período existe em 1 ou 2 das 3 demonstrações, mas não nas 3 (por isso foi descartado)."""
    descartadas = (datas_dre | datas_bp | datas_dfc) - datas_comuns
    if not descartadas:
        return
    print("\n⚠️ Períodos descartados por não existirem nas 3 demonstrações ao mesmo tempo:")
    for data in sorted(descartadas):
        presentes = [
            nome for nome, conjunto in [("DRE", datas_dre), ("Balanço", datas_bp), ("DFC", datas_dfc)]
            if data in conjunto
        ]
        print(f"   {data} — só tinha em: {', '.join(presentes)}")


def _avisar_buracos_no_meio(datas_ordenadas: list, limite_dias: int = 110) -> None:
    """
    Avisa quando falta um trimestre inteiro NO MEIO da série final já alinhada
    (nenhuma das 3 demonstrações tem dado pra aquele trimestre — ex: empresa
    não publicou nada naquele período). limite_dias ~110 = mais de 1 trimestre
    de intervalo entre duas datas consecutivas.
    """
    for anterior, atual in zip(datas_ordenadas, datas_ordenadas[1:]):
        dias = (pd.Timestamp(atual) - pd.Timestamp(anterior)).days
        if dias > limite_dias:
            print(f"⚠️ Buraco na série: nenhuma demonstração tem dado entre {anterior} e {atual} "
                  f"(~{dias} dias sem nenhum trimestre — a empresa pode não ter publicado nesse intervalo)")


def alinhar_periodos(dre: pd.DataFrame, balanco: pd.DataFrame, dfc: pd.DataFrame) -> tuple:
    """
    Garante que DRE, Balanço e DFC tenham exatamente os MESMOS períodos
    (mesma data final), para que sejam comparáveis lado a lado.

    O Balanço só tem comparativo com o fechamento anual anterior (31/12), não
    com o mesmo trimestre do ano anterior como a DRE/DFC têm — por isso, para
    anos alcançados só via comparativo (sem um envio de ITR próprio), o
    Balanço não tem 1T/2T/3T enquanto a DRE tem. Nesse caso, a interseção é o
    que realmente pode ser comparado nas três demonstrações.

    Avisa no console sempre que descarta um período por inconsistência entre
    as 3 demonstrações, e sempre que sobra um buraco de trimestre inteiro no
    meio da série final (ex: ano de 2018 sumido).
    """
    datas_dre = {_data_fim(c) for c in dre.columns}
    datas_bp = {_data_fim(c) for c in balanco.columns}
    datas_dfc = {_data_fim(c) for c in dfc.columns}
    datas_comuns = datas_dre & datas_bp & datas_dfc

    _avisar_periodos_descartados(datas_dre, datas_bp, datas_dfc, datas_comuns)

    dre = dre[[c for c in dre.columns if _data_fim(c) in datas_comuns]]
    balanco = balanco[[c for c in balanco.columns if _data_fim(c) in datas_comuns]]
    dfc = dfc[[c for c in dfc.columns if _data_fim(c) in datas_comuns]]

    _avisar_buracos_no_meio(sorted(datas_comuns))

    return dre, balanco, dfc


def somente_trimestre_isolado(tabela: pd.DataFrame, limite_dias: int = 100) -> pd.DataFrame:
    """
    Mantém só as colunas de período "isolado" (~3 meses), descartando as
    acumuladas no ano (que têm a MESMA data final que a coluna isolada do
    mesmo trimestre, e por isso geram cabeçalhos duplicados/ambíguos).
    """
    if tabela.empty:
        return tabela

    def eh_isolado(rotulo: str) -> bool:
        if " a " not in rotulo:
            return True  # não tem período (ex: Balanço, que é data única)
        inicio, fim = rotulo.split(" a ")
        dias = (pd.Timestamp(fim) - pd.Timestamp(inicio)).days
        return dias <= limite_dias

    colunas_mantidas = [c for c in tabela.columns if eh_isolado(c)]
    # calcular_quarto_trimestre() acrescenta as colunas de 4T no fim da lista,
    # fora de ordem cronológica — reordena pela data final de cada período.
    colunas_mantidas = sorted(colunas_mantidas, key=lambda c: c.split(" a ")[-1])
    return tabela[colunas_mantidas]


def _formatar_rotulo_data(rotulo: str, modo: str) -> str:
    """
    modo="unica":    "2024-09-30" -> "30/09/24"
    modo="fim":      "2024-01-01 a 2024-03-31" -> "31/03/24" (só a data final)
    modo="intervalo":"2024-01-01 a 2024-09-30" -> "01/01/2024-30/09/2024"
    """
    if modo == "unica":
        return pd.Timestamp(rotulo).strftime("%d/%m/%y")

    inicio, fim = rotulo.split(" a ")
    if modo == "fim":
        return pd.Timestamp(fim).strftime("%d/%m/%y")
    if modo == "intervalo":
        return f"{pd.Timestamp(inicio).strftime('%d/%m/%Y')}-{pd.Timestamp(fim).strftime('%d/%m/%Y')}"
    raise ValueError(f"modo inválido: {modo}")


def preparar_bloco(tabela: pd.DataFrame, classificacao: dict, modo_data: str) -> pd.DataFrame:
    """
    Prepara um bloco (DRE, Balanço ou DFC) para exportação final:
    - classifica cada conta (total/subtotal/detalhe) e guarda em df.attrs["estilos"]
    - remove o nível CD_CONTA do índice (só DS_CONTA aparece no Excel)
    - formata os rótulos de coluna (datas)
    - substitui vazios por 0
    """
    if tabela.empty:
        tabela = tabela.copy()
        tabela.attrs["estilos"] = []
        return tabela

    estilos = [classificacao.get(cod, "detalhe") for cod in tabela.index.get_level_values("CD_CONTA")]

    tabela = tabela.droplevel("CD_CONTA").copy()
    tabela.columns = [_formatar_rotulo_data(c, modo_data) for c in tabela.columns]
    tabela = tabela.fillna(0)
    tabela.attrs["estilos"] = estilos
    return tabela
