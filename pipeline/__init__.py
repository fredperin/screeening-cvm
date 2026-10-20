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


# ---------------- Chaves de acesso nunca vão para arquivos publicados ----------------
# Algumas APIs repetem a chave na mensagem de erro (o BLS: "The key:XXXX provided by the User is invalid";
# o requests: o endereço com ?api_key=XXXX). Todo texto de erro que vai para site/ ou para o alerta passa por aqui.
NOMES_SEGREDOS = ("FRED_API_KEY", "BLS_API_KEY", "SEC_USER_AGENT")


def sem_segredos(texto):
    import os
    import re
    if not isinstance(texto, str):
        return texto
    for nome in NOMES_SEGREDOS:
        valor = os.environ.get(nome, "")
        if len(valor) >= 6:
            texto = texto.replace(valor, "[chave oculta]")
    texto = re.sub(r"(?i)(api_key=)[^&\s'\"]+", r"\1[chave oculta]", texto)
    texto = re.sub(r"(?i)(registrationkey['\"]?\s*[:=]\s*['\"]?)[^'\"\s,}]+", r"\1[chave oculta]", texto)
    texto = re.sub(r"(?i)(the key\s*:?\s*)[0-9a-f]{16,}", r"\1[chave oculta]", texto)
    return texto
