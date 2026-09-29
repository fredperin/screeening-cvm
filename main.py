"""
main.py — Busca o ITR de uma empresa na CVM e exporta para Excel.

Uso:
    py main.py "PETROBRAS" 2024                  # um ano só
    py main.py "PETROBRAS" 2015 2024              # faixa de anos (histórico)
    py main.py "33.000.167/0001-01" 2024 --tipo ind
"""

import argparse

from src.cvm_itr import (
    buscar_cnpj, buscar_itr, buscar_dados_cadastrais, buscar_dados_fca, montar_documento_padrao, _normalizar_cnpj,
)
from src.exportar import exportar_documento_padrao


def main():
    parser = argparse.ArgumentParser(description="Busca ITR (CVM) e exporta para Excel")
    parser.add_argument("empresa", help="Nome da empresa (busca parcial) ou CNPJ")
    parser.add_argument("ano_inicio", type=int, help="Ano inicial do ITR, ex: 2015")
    parser.add_argument("ano_fim", type=int, nargs="?", default=None,
                         help="Ano final (opcional). Se omitido, busca só ano_inicio.")
    parser.add_argument("--tipo", choices=["con", "ind"], default="con",
                         help="con = consolidado (default), ind = individual")
    args = parser.parse_args()

    ano_fim = args.ano_fim or args.ano_inicio
    anos = list(range(args.ano_inicio, ano_fim + 1))

    is_cnpj = len(_normalizar_cnpj(args.empresa)) == 14

    if is_cnpj:
        cnpj = args.empresa
        nome_empresa = args.empresa
    else:
        print(f"🔎 Buscando CNPJ para '{args.empresa}' em {ano_fim}...")
        candidatos = buscar_cnpj(args.empresa, ano_fim)
        if candidatos.empty:
            print("❌ Nenhuma empresa encontrada com esse nome.")
            return
        if len(candidatos) > 1:
            print("⚠️ Mais de uma empresa encontrada, usando a primeira:")
            print(candidatos.to_string(index=False))
        linha = candidatos.iloc[0]
        cnpj = linha["CNPJ_CIA"]
        nome_empresa = linha["DENOM_CIA"]
        print(f"✅ {nome_empresa} — CNPJ {cnpj}")

    demonstracoes = buscar_itr(cnpj, anos, tipo=args.tipo)
    blocos = montar_documento_padrao(demonstracoes, ano_inicio=args.ano_inicio)
    dados_cadastrais = {**buscar_dados_cadastrais(cnpj), **buscar_dados_fca(cnpj)}
    exportar_documento_padrao(blocos, nome_empresa, args.ano_inicio, ano_fim, dados_cadastrais=dados_cadastrais)


if __name__ == "__main__":
    main()
