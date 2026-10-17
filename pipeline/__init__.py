"""
Pipeline da plataforma R.V. Mapp: baixa CVM, B3, Banco Central e Tesouro e
gera os arquivos estáticos que o site (pasta site/) lê.

Saídas:
- data/pipeline/   intermediários (Parquet), não versionados
- site/dados/      JSON consumidos pelo site
- site/downloads/  Excel padrão pronto de cada empresa
"""

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_INTERMEDIARIO = RAIZ / "data" / "pipeline"
DIR_DADOS_SITE = RAIZ / "site" / "dados"
DIR_DOWNLOADS_SITE = RAIZ / "site" / "downloads"

for _d in (DIR_INTERMEDIARIO, DIR_DADOS_SITE, DIR_DOWNLOADS_SITE):
    _d.mkdir(parents=True, exist_ok=True)
