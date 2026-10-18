"""
Resumos aprofundados das empresas acompanhadas (opção 1 da Fase B).

Cada resumo é um arquivo Markdown versionado em conteudo/resumos/{TICKER}.md, escrito
sob demanda (a pedido do usuário) a partir do Formulário de Referência e de outros
documentos. Este módulo só converte para o site: site/dados/resumos/{id}.json.

Formato do .md: primeira linha "# Título"; linha opcional "Atualizado em: AAAA-MM-DD";
"## Seção", parágrafos, listas com "- " e **negrito**.
Uso: py -m pipeline.resumos
"""

import html
import json
import re

from pipeline import DIR_DADOS_SITE, RAIZ

DIR_FONTE = RAIZ / "conteudo" / "resumos"
DIR_SITE = DIR_DADOS_SITE / "resumos"


def _inline(texto):
    t = html.escape(texto)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)


def markdown_para_html(md):
    titulo, atualizado, partes, lista, paragrafo = None, None, [], [], []

    def fechar():
        if paragrafo:
            partes.append(f"<p>{_inline(' '.join(paragrafo))}</p>")
            paragrafo.clear()
        if lista:
            partes.append("<ul>" + "".join(f"<li>{_inline(i)}</li>" for i in lista) + "</ul>")
            lista.clear()

    for linha in md.splitlines():
        l = linha.strip()
        if not l:
            fechar()
        elif l.startswith("# ") and titulo is None:
            titulo = l[2:].strip()
        elif l.lower().startswith("atualizado em:"):
            atualizado = l.split(":", 1)[1].strip()
        elif l.startswith("### "):
            fechar()
            partes.append(f"<h4>{_inline(l[4:])}</h4>")
        elif l.startswith("## "):
            fechar()
            partes.append(f"<h3>{_inline(l[3:])}</h3>")
        elif l.startswith(("- ", "* ")):
            if paragrafo:
                fechar()
            lista.append(l[2:])
        else:
            if lista:
                fechar()
            paragrafo.append(l)
    fechar()
    return titulo, atualizado, "\n".join(partes)


def gerar():
    DIR_SITE.mkdir(parents=True, exist_ok=True)
    gerados = set()
    for arq in sorted(DIR_FONTE.glob("*.md")) if DIR_FONTE.exists() else []:
        id_ = arq.stem.upper()
        titulo, atualizado, corpo = markdown_para_html(arq.read_text(encoding="utf-8"))
        (DIR_SITE / f"{id_}.json").write_text(json.dumps(
            {"id": id_, "titulo": titulo, "atualizado": atualizado, "html": corpo},
            ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        gerados.add(f"{id_}.json")
    for velho in DIR_SITE.glob("*.json"):  # resumo apagado da pasta conteudo/ sai do site
        if velho.name not in gerados:
            velho.unlink()
    print(f"✅ resumos aprofundados: {len(gerados)}")
    return len(gerados)


if __name__ == "__main__":
    gerar()
