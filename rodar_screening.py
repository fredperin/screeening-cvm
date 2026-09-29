"""
rodar_screening.py — Gera a tabela de screening de todas as empresas não
financeiras da B3 (fundamentos CVM + preço/mercado yfinance).

Além do Excel de sempre (data/processed/), salva um CSV em data/screening/
que É versionado no Git — é esse arquivo que o dashboard publicado no
Streamlit Cloud lê, pra não precisar rodar o pipeline pesado (yfinance pra
~280 empresas) toda vez que alguém abre o site.

Uso:
    py rodar_screening.py                # ano fiscal mais recente disponível
    py rodar_screening.py 2024           # força um ano fiscal específico
"""

import sys
from datetime import date
from pathlib import Path

from config.config import BASE_DIR
from src.screening import montar_screening
from src.exportar_screening import exportar_screening, salvar_csv_publico

ano_fiscal = int(sys.argv[1]) if len(sys.argv) > 1 else None

tabela = montar_screening(ano_fiscal)

# CSV primeiro (é o que o dashboard publicado precisa) — se o Excel local
# estiver aberto e travar a escrita, pelo menos isso já foi salvo, sem
# precisar repetir os ~7-8 minutos de consultas ao yfinance.
caminho_csv = BASE_DIR / "data" / "screening" / "screening_atual.csv"
salvar_csv_publico(tabela, caminho_csv)

caminho_data = BASE_DIR / "data" / "screening" / "ultima_atualizacao.txt"
caminho_data.write_text(date.today().isoformat(), encoding="utf-8")
print(f"📅 Data da atualização registrada: {date.today().isoformat()}")

exportar_screening(tabela, ano_fiscal)
