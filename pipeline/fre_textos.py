"""
Trechos oficiais do Formulário de Referência (opção "recorte automático", sem IA).

O pacote do FRE na CVM é um XML em que cada seção de texto vem como um PDF embutido.
Para cada empresa, baixa o FRE mais recente (só quando sai versão nova), extrai o texto
das seções que descrevem o negócio e publica um trecho de cada uma.

Saídas: data/pipeline/fre_textos/{id}.json (texto completo, cache — base para os
resumos aprofundados) e site/dados/negocio/{id}.json (trechos para o site).
Uso: py -m pipeline.fre_textos [TICKER ...]
"""

import base64
import io
import logging
import json
import re
import sys
import time
import zipfile

import requests

from pipeline import DIR_DADOS_SITE, DIR_INTERMEDIARIO

SECOES = {
    "AtividadesEmissorControladas": "Atividades da empresa e controladas",
    "InfoSegmentosOperacionais": "Segmentos operacionais",
    "ProducaoComercializacaoMercados": "Produção, comercialização e mercados",
    "PrincipaisClientes": "Principais clientes",
    "PlanoNegocios": "Plano de negócios",
    "Descricao5PrincipaisFatoresRisco": "Cinco principais fatores de risco",
    "HistoricoEmissor": "Histórico",
}
LIMITE_TRECHO = 3000
DIR_CACHE = DIR_INTERMEDIARIO / "fre_textos"
DIR_SITE = DIR_DADOS_SITE / "negocio"
logging.getLogger("pypdf").setLevel(logging.ERROR)  # avisos de fonte dos PDFs, sem efeito no texto


def _limpar(texto):
    """Junta as linhas quebradas do PDF em parágrafos."""
    linhas = [l.strip() for l in texto.replace("\r", "").split("\n")]
    paragrafos, atual = [], ""
    for l in linhas:
        if not l:
            if atual:
                paragrafos.append(atual)
                atual = ""
            continue
        atual = f"{atual} {l}".strip() if atual else l
        if re.search(r"[.:;!?]$", l) and len(atual) > 80:
            paragrafos.append(atual)
            atual = ""
    if atual:
        paragrafos.append(atual)
    texto = "\n\n".join(re.sub(r"\s{2,}", " ", p) for p in paragrafos)
    return re.sub(r"(?<=\w)- (?=\w)", "", texto).strip()


def _texto_secao(xml, tag):
    m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.S)
    if not m:
        return None
    bloco = m.group(1)
    pdf = re.search(r"<ImagemObjetoArquivoPdf>(.*?)</ImagemObjetoArquivoPdf>", bloco, re.S)
    if pdf:
        from pypdf import PdfReader
        try:
            leitor = PdfReader(io.BytesIO(base64.b64decode(pdf.group(1))))
            return _limpar("\n".join((p.extract_text() or "") for p in leitor.pages)) or None
        except Exception:
            return None
    texto = re.sub(r"<[^>]+>", " ", bloco)
    return _limpar(texto) if len(texto.strip()) > 40 else None


def baixar_xml(link):
    url = link.replace("http://", "https://")
    for tentativa in range(3):
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=180)
            r.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                nomes = [n for n in z.namelist() if n.lower().endswith(".xml") and "cadastral" not in n.lower()]
                if not nomes:
                    return None
                return z.read(max(nomes, key=lambda n: z.getinfo(n).file_size)).decode("latin1")
        except (requests.RequestException, zipfile.BadZipFile):
            time.sleep(5 * (tentativa + 1))
    return None


def _trecho(texto):
    if not texto or len(texto) <= LIMITE_TRECHO:
        return texto, False
    corte = texto.rfind("\n\n", 0, LIMITE_TRECHO)
    corte = corte if corte > LIMITE_TRECHO * 0.5 else texto.rfind(". ", 0, LIMITE_TRECHO) + 1
    return texto[:corte].strip(), True


def _processar(ficha):
    """Retorna ('baixado'|'cache'|'sem_fre'|'falha', id)."""
    id_ = ficha["id"]
    fre = ficha.get("fre")
    if not fre or not fre.get("link"):
        return "sem_fre", id_
    cache = DIR_CACHE / f"{id_}.json"
    dados = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else None
    situacao = "cache"
    if not dados or dados.get("link") != fre["link"]:
        xml = baixar_xml(fre["link"])
        if xml is None:
            return "falha", id_
        dados = {"id": id_, "link": fre["link"], "referencia": fre["referencia"], "versao": fre["versao"],
                 "secoes": {nome: _texto_secao(xml, tag) for tag, nome in SECOES.items()}}
        cache.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        situacao = "baixado"

    secoes = []
    for nome in SECOES.values():
        trecho, cortado = _trecho(dados["secoes"].get(nome))
        if trecho:
            secoes.append({"titulo": nome, "texto": trecho, "cortado": cortado})
    (DIR_SITE / f"{id_}.json").write_text(json.dumps({
        "id": id_, "fonte": f"Formulário de Referência {dados['referencia'][:4]} (versão {dados['versao']})",
        "link": dados["link"], "secoes": secoes}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return situacao, id_


def gerar(filtro=None, paralelos=6):
    from concurrent.futures import ThreadPoolExecutor

    DIR_CACHE.mkdir(parents=True, exist_ok=True)
    DIR_SITE.mkdir(parents=True, exist_ok=True)
    fichas = [json.loads(a.read_text(encoding="utf-8")) for a in sorted((DIR_DADOS_SITE / "fichas").glob("*.json"))]
    fichas = [f for f in fichas if not filtro or f["id"] in filtro]
    contagem = {"baixado": 0, "cache": 0, "sem_fre": 0, "falha": 0}
    with ThreadPoolExecutor(max_workers=paralelos) as pool:
        for situacao, id_ in pool.map(_processar, fichas):
            contagem[situacao] += 1
            if situacao == "falha":
                print(f"   ⚠️ {id_}: não consegui baixar o FRE")
    print(f"✅ textos do FRE: {contagem['baixado']} baixados, {contagem['cache']} sem mudança, "
          f"{contagem['sem_fre']} sem FRE, {contagem['falha']} falhas")
    if contagem["falha"] > 0.3 * max(len(fichas), 1):
        raise RuntimeError(f"{contagem['falha']} FREs não baixaram")
    return contagem


if __name__ == "__main__":
    gerar(set(sys.argv[1:]) or None)
