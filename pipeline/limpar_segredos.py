"""
Última barreira antes de publicar: procura o valor das chaves (FRED_API_KEY, BLS_API_KEY, SEC_USER_AGENT)
e padrões de chave em mensagens de erro em todos os arquivos de texto de site/ e no alerta do GitHub,
e troca por "[chave oculta]". Roda no GitHub Actions depois da atualização e antes da publicação.

Uso: py -m pipeline.limpar_segredos
"""

from pipeline import DIR_INTERMEDIARIO, RAIZ, sem_segredos

EXTENSOES = {".json", ".html", ".js", ".csv", ".txt", ".md", ".xml"}


def main():
    alvos = [p for p in (RAIZ / "site").rglob("*") if p.is_file() and p.suffix in EXTENSOES]
    alvos.append(DIR_INTERMEDIARIO / "alerta.md")
    trocados = []
    for p in alvos:
        if not p.exists():
            continue
        try:
            texto = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        limpo = sem_segredos(texto)
        if limpo != texto:
            p.write_text(limpo, encoding="utf-8")
            trocados.append(str(p.relative_to(RAIZ)))
    print(f"🔒 chaves ocultadas em {len(trocados)} arquivo(s): {trocados or 'nenhum'}")


if __name__ == "__main__":
    main()
