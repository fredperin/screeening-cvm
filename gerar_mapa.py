"""Gera o mapa de contas (estrutura, sem valores) de uma empresa para referência."""

import sys

from config.config import PROCESSED_DIR
from src.cvm_itr import buscar_cnpj
from src.mapa_contas import gerar_mapa_contas, exportar_mapa_contas

empresa = sys.argv[1] if len(sys.argv) > 1 else "WEG"
ano = int(sys.argv[2]) if len(sys.argv) > 2 else 2024

candidatos = buscar_cnpj(empresa, ano)
linha = candidatos.iloc[0]
cnpj, denom = linha["CNPJ_CIA"], linha["DENOM_CIA"]
print(f"✅ {denom} — CNPJ {cnpj}")

mapas = gerar_mapa_contas(cnpj, ano)

slug = "".join(c if c.isalnum() else "_" for c in denom).strip("_")[:20]
caminho = PROCESSED_DIR / f"{slug}_mapa_contas_{ano}.xlsx"
exportar_mapa_contas(mapas, caminho)
