"""
mapa_contas.py — Gera o "mapa de contas" (estrutura, sem valores) de uma empresa,
para apoiar a escolha de quais contas entram no padrão do projeto.

Diferente de buscar_itr() (que traz os valores por período), aqui o objetivo é
só listar CD_CONTA + DS_CONTA + nível hierárquico, uma linha por conta única.
"""

import pandas as pd

from config.config import DEMONSTRACOES_ITR
from src.cvm_itr import _ler_demonstracao, _normalizar_descricoes


def _mapa_demonstracao(bruto: pd.DataFrame) -> pd.DataFrame:
    """Reduz um DataFrame bruto do ITR a uma lista única de contas, com nível hierárquico."""
    if bruto.empty:
        return bruto

    bruto = _normalizar_descricoes(bruto)
    mapa = bruto[["CD_CONTA", "DS_CONTA"]].drop_duplicates().sort_values("CD_CONTA")
    mapa["NIVEL"] = mapa["CD_CONTA"].str.count(r"\.") + 1
    return mapa.reset_index(drop=True)


def gerar_mapa_contas(cnpj: str, ano: int, tipo: str = "con") -> dict:
    """
    Gera o mapa de contas (BPA, BPP, DRE, DFC_MI) de uma empresa em um ano,
    sem valores — só a estrutura (código, descrição, nível).

    Args:
        cnpj:  CNPJ da empresa
        ano:   ano de referência do ITR
        tipo:  "con" (consolidado) ou "ind" (individual)
    Returns:
        dict {"Balanço Patrimonial Ativo": df, ...} (sem a DMPL, que tem estrutura própria)
    """
    resultado = {}
    for sigla, titulo in DEMONSTRACOES_ITR.items():
        if sigla == "DMPL":
            continue  # a DMPL não tem um "plano de contas" no mesmo sentido — é sempre a mesma estrutura de mutações

        bruto = _ler_demonstracao(ano, sigla, tipo, cnpj)
        if bruto.empty and tipo == "con":
            bruto = _ler_demonstracao(ano, sigla, "ind", cnpj)

        resultado[titulo] = _mapa_demonstracao(bruto)

    return resultado


def exportar_mapa_contas(mapas: dict, caminho) -> None:
    """Exporta o mapa de contas para um Excel simples, uma aba por demonstração."""
    from src.exportar import _caminho_longo, _formatar

    with pd.ExcelWriter(_caminho_longo(caminho), engine="openpyxl") as writer:
        for titulo, df in mapas.items():
            if df is None or df.empty:
                continue
            df.to_excel(writer, sheet_name=titulo[:31], index=False)
            print(f"  ✅ Aba '{titulo[:31]}' exportada ({len(df)} contas)")

    _formatar(caminho)
    print(f"\n📁 Mapa de contas salvo: {caminho}")
