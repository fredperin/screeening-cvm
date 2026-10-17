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


def isolar_trimestres(tabela: pd.DataFrame, limite_dias: int = 100, preferir_derivado: bool = False) -> pd.DataFrame:
    """
    Devolve só colunas de trimestre isolado, para QUALQUER ano fiscal (jan-dez,
    abr-mar como São Martinho/Raízen, mar-fev como Camil).

    A CVM publica períodos acumulados desde o início do exercício (e, na DRE do
    ITR, também o trimestre isolado). Cada trimestre isolado que não vier pronto
    é obtido pela diferença entre dois acumulados com o MESMO início, separados
    por ~3 meses: 2T = 6M − 3M, 3T = 9M − 6M, 4T = 12M (DFP) − 9M. Se faltar um
    acumulado, o trimestre que depende dele não é calculado — nunca gera número errado.

    Quando a CVM traz o trimestre isolado pronto E ele também pode ser derivado, os
    dois podem divergir (reapresentações). Regra, igual à do documento padrão original:
    o último trimestre do exercício (12M − 9M) e, com preferir_derivado (DFC), todos
    os trimestres usam o valor derivado; os demais usam o isolado publicado.
    """
    if tabela.empty:
        return tabela

    def limites(rotulo):
        inicio, fim = rotulo.split(" a ")
        return pd.Timestamp(inicio), pd.Timestamp(fim)

    com_periodo = [c for c in tabela.columns if " a " in c]
    isolados = {c: tabela[c] for c in com_periodo if (limites(c)[1] - limites(c)[0]).days <= limite_dias}

    por_inicio = {}
    for c in com_periodo:
        por_inicio.setdefault(c.split(" a ")[0], []).append(c)
    for grupo in por_inicio.values():
        grupo = sorted(grupo, key=lambda c: c.split(" a ")[1])
        for anterior, atual in zip(grupo, grupo[1:]):
            fim_anterior, fim_atual = limites(anterior)[1], limites(atual)[1]
            if not 80 <= (fim_atual - fim_anterior).days <= 100:
                continue
            rotulo = f"{(fim_anterior + pd.Timedelta(days=1)).date()} a {fim_atual.date()}"
            anual = (fim_atual - limites(atual)[0]).days >= 360
            if preferir_derivado or anual:
                isolados[rotulo] = tabela[atual] - tabela[anterior]
            else:
                isolados.setdefault(rotulo, tabela[atual] - tabela[anterior])

    ordem = sorted(isolados, key=lambda c: c.split(" a ")[1])
    return pd.DataFrame({c: isolados[c] for c in ordem}, index=tabela.index)


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
    # Empresa que publica a DFC só pelo método direto (ex: Belora, Revee) fica sem DFC
    # indireta: alinha só DRE e Balanço, em vez de zerar a interseção.
    conjuntos = [d for d in (datas_dre, datas_bp, datas_dfc) if d]
    datas_comuns = set.intersection(*conjuntos) if conjuntos else set()

    _avisar_periodos_descartados(datas_dre, datas_bp, datas_dfc, datas_comuns)

    dre = dre[[c for c in dre.columns if _data_fim(c) in datas_comuns]]
    balanco = balanco[[c for c in balanco.columns if _data_fim(c) in datas_comuns]]
    dfc = dfc[[c for c in dfc.columns if _data_fim(c) in datas_comuns]]

    _avisar_buracos_no_meio(sorted(datas_comuns))

    return dre, balanco, dfc


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

    codigos = list(tabela.index.get_level_values("CD_CONTA"))
    estilos = [classificacao.get(cod, "detalhe") for cod in codigos]

    tabela = tabela.droplevel("CD_CONTA").copy()
    tabela.columns = [_formatar_rotulo_data(c, modo_data) for c in tabela.columns]
    tabela = tabela.fillna(0)
    tabela.attrs["estilos"] = estilos
    tabela.attrs["codigos"] = codigos  # usado pela aba de indicadores pra achar cada conta na planilha
    return tabela
