"""Configuração central do projeto de dados CVM."""

import sys
from pathlib import Path

# Os prints do projeto usam emojis (📁, ✅, ⚠️) pra facilitar leitura no
# terminal. Alguns ambientes (Streamlit, tarefas agendadas, alguns consoles
# do Windows) não abrem o stdout em UTF-8 por padrão e derrubam o processo
# com UnicodeEncodeError na primeira emoji. Força UTF-8 aqui, uma vez, pra
# todo o projeto — assim funciona igual em qualquer jeito de rodar o código.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

CVM_BASE_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS"

# DFP = Demonstrações Financeiras Padronizadas (dados ANUAIS). O ITR só cobre
# 1T/2T/3T — o resultado do 4º trimestre isolado não existe em lugar nenhum
# da CVM pronto; é derivado como Ano Completo (DFP) menos Acumulado Jan-Set (ITR).
CVM_BASE_URL_DFP = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS"

# Cadastro geral de companhias abertas (setor, situação, tipo de mercado,
# categoria de registro, controle acionário, auditor etc.) — dado cadastral,
# não financeiro. Um arquivo único (~1,5 MB) com todas as ~2.700 empresas já
# registradas historicamente, sem separação por ano.
CVM_BASE_URL_CAD = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS"

# FCA = Formulário Cadastral. Complementa o CAD com descrição do negócio em
# texto livre, ticker(s) de negociação e segmento de listagem na B3 (Novo
# Mercado, Nível 1/2, Tradicional). Publicado por ano, como o ITR/DFP.
CVM_BASE_URL_FCA = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FCA/DADOS"

# Demonstrações do ITR que o projeto extrai, na ordem em que aparecem no Excel final.
DEMONSTRACOES_ITR = {
    "BPA": "Balanço Patrimonial Ativo",
    "BPP": "Balanço Patrimonial Passivo",
    "DRE": "Demonstração do Resultado",
    "DFC_MI": "Demonstração do Fluxo de Caixa (Método Indireto)",
    "DMPL": "Demonstração das Mutações do Patrimônio Líquido",
}
