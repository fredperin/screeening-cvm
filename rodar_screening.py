"""
rodar_screening.py — Gera a tabela de screening de todas as empresas não
financeiras da B3 (fundamentos CVM + preço/mercado yfinance).

Uso:
    py rodar_screening.py                # ano fiscal mais recente disponível
    py rodar_screening.py 2024           # força um ano fiscal específico
"""

import sys

from src.screening import montar_screening
from src.exportar_screening import exportar_screening

ano_fiscal = int(sys.argv[1]) if len(sys.argv) > 1 else None

tabela = montar_screening(ano_fiscal)
exportar_screening(tabela, ano_fiscal)
