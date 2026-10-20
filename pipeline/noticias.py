"""
Manchetes de fontes oficiais e públicas (só título, data e link para a matéria original).

Onshore, dois tipos:
- oficiais: Banco Central (notícias e comunicados do Copom), IBGE (Agência de Notícias),
  CVM e Agência Brasil (economia e política);
- mercado: RSS públicos de jornais e sites de economia e política — só a manchete com link
  para o jornal (o texto continua no site de cada um).
Cada manchete recebe uma categoria — política, economia e finanças ou empresas — pela editoria
de origem (o feed da seção ou a seção no endereço da matéria); manchete de economia que cita uma
empresa da lista vai para empresas. As que citam uma empresa do universo (pelo ticker ou pelo nome
de pregão da B3) ficam ligadas a ela.

Os feeds só trazem as últimas matérias de cada fonte; por isso a coleta roda na atualização diária
e mais 3x ao dia (junto com o Tesouro) e cada rodada soma as manchetes novas às já guardadas
(o arquivo local e o publicado no site). As manchetes ligadas a empresas ficam guardadas por
DIAS_EMPRESAS dias em noticias_empresas.json, usado na aba "Eventos e notícias" de cada empresa.

Saída: site/dados/noticias.json e site/dados/noticias_empresas.json. Uso: py -m pipeline.noticias
"""

import html
import json
import re
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

from pipeline import DIR_DADOS_SITE

CABECALHO = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"}
DIAS = 45          # oficiais
DIAS_MERCADO = 7   # jornais: volume alto, só a última semana
MAXIMO = 3000
DIAS_EMPRESAS = 180  # histórico das manchetes ligadas a empresas
MAXIMO_EMPRESAS = 12000
FUSO_BR = timezone(timedelta(hours=-3))

# (fonte, endereço, categoria): "url" = categoria pela seção no endereço de cada matéria
FEEDS = [
    ("Banco Central", "https://www.bcb.gov.br/api/feed/sitebcb/sitefeeds/noticias", "economia"),
    ("Banco Central — Copom", "https://www.bcb.gov.br/api/feed/sitebcb/sitefeeds/comunicadoscopom", "economia"),
    ("CVM", "https://www.gov.br/cvm/pt-br/assuntos/noticias/{ano}/RSS", "economia"),
    ("Agência Brasil", "https://agenciabrasil.ebc.com.br/rss/economia/feed.xml", "economia"),
    ("Agência Brasil", "https://agenciabrasil.ebc.com.br/rss/politica/feed.xml", "politica"),
]
FEEDS_MERCADO = [
    ("Valor Econômico", "https://pox.globo.com/rss/valor/", "url"),
    ("Folha", "https://feeds.folha.uol.com.br/mercado/rss091.xml", "economia"),
    ("Folha", "https://feeds.folha.uol.com.br/poder/rss091.xml", "politica"),
    ("Estadão", "https://www.estadao.com.br/arc/outboundfeeds/feeds/rss/sections/economia/", "economia"),
    ("Estadão", "https://www.estadao.com.br/arc/outboundfeeds/feeds/rss/sections/politica/", "politica"),
    ("g1", "https://g1.globo.com/rss/g1/economia/", "economia"),
    ("g1", "https://g1.globo.com/rss/g1/politica/", "politica"),
    ("Poder360", "https://www.poder360.com.br/feed/", "url"),
    ("InfoMoney", "https://www.infomoney.com.br/feed/", "url"),
    ("Brazil Journal", "https://braziljournal.com/feed/", "empresas"),
    ("NeoFeed", "https://neofeed.com.br/feed/", "url"),
    ("Pipeline (Valor)", "https://pipelinevalor.globo.com/rss/pipelinevalor/", "url"),
    ("Bloomberg Línea", "https://www.bloomberglinea.com.br/arc/outboundfeeds/rss/?outputType=xml", "url"),
    ("Money Times", "https://www.moneytimes.com.br/feed/", "economia"),
]
DESCARTAR = ("patrocinado", "estilo-de-vida", "esport", "day-off", "video", "podcast", "carros", "horoscopo", "cultura", "viagem")


def categoria_pela_url(link, padrao):
    """Seção do endereço da matéria -> categoria (None = fora do escopo, ex.: conteúdo patrocinado, esportes)."""
    secao = re.sub(r"^https?://[^/]+/", "", link).split("/")[0].lower()
    if any(k in secao for k in DESCARTAR):
        return None
    if "economia" in secao or "financas" in secao or "mercado" in secao or "investir" in secao:
        return "economia"
    if "politica" in secao or "eleic" in secao or secao == "poder":
        return "politica"
    if any(k in secao for k in ("empresas", "negocios", "startups", "tech")):
        return "empresas"
    if secao in ("brasil", "mundo", "agronegocios", "legislacao", "internacional"):
        return "economia"
    return "politica" if padrao == "url" and "poder" in secao else (padrao if padrao != "url" else "economia")
URL_IBGE = "https://servicodados.ibge.gov.br/api/v3/noticias/?qtd=60&tipo=noticia,release"

# Ligação manchete -> empresa: ticker, nome de pregão da B3 sem sufixos e nomes pelos quais a imprensa chama a empresa
SUFIXOS = {"S/A", "S.A.", "S.A", "SA", "ON", "PN", "PART", "PARTICIPACOES"}
GENERICOS = {"BRASIL", "BANCO", "ENERGIA", "SANEAMENTO", "GAS", "CIA", "GRUPO", "REDE", "SAO", "LOG", "MELHOR", "UNIAO",
             "OURO", "SANTOS", "FUTURO", "CENTRAL", "NORTE", "SUL", "VALOR", "ACO", "PAR", "TEC", "MULTI"}
# nomes que também são palavras comuns: só valem com inicial maiúscula fora do começo da manchete (ou em maiúsculas)
AMBIGUOS = {"VALE", "RUMO", "VAMOS", "TIM", "AZUL", "TENDA", "VESTE", "VIVER", "EVEN", "VALID", "MOVIDA", "CRISTAL", "ESTRELA",
            "MUNDIAL", "RENOVA", "NATURA", "DIRECIONAL", "COMPASS", "HERCULES", "CEDRO", "MILLS", "ROMI", "BRAVA", "VIVO", "PRIO",
            "DESKTOP", "ALLIED", "DOTZ", "MITRE", "MATER DEI", "SER EDUCA", "VITTIA", "DIMED", "SCHULZ", "UNICASA", "IRANI"}
APELIDOS_EXTRAS = {
    "MAGAZ LUIZA": ["MAGAZINE LUIZA", "MAGALU"], "P.ACUCAR-CBD": ["PAO DE ACUCAR", "GPA"], "RAIADROGASIL": ["RAIA DROGASIL", "RD SAUDE"],
    "SID NACIONAL": ["CSN", "SIDERURGICA NACIONAL"], "CSNMINERACAO": ["CSN MINERACAO"], "TELEF BRASIL": ["TELEFONICA"],  # "Vivo" fica de fora: confunde com "ao vivo"
    "M.DIASBRANCO": ["M. DIAS BRANCO", "M.DIAS BRANCO"], "IOCHP-MAXION": ["IOCHPE"], "REDE D OR": ["REDE D'OR", "REDE DOR"],
    "LOJAS RENNER": ["RENNER"], "RANDON PART": ["RANDON", "RANDONCORP"], "ISA ENERGIA": ["ISA CTEEP"], "MOTIVA SA": ["MOTIVA", "CCR"],
    "AXIA ENERGIA": ["AXIA", "ELETROBRAS"], "ENGIE BRASIL": ["ENGIE"], "CPFL ENERGIA": ["CPFL"], "CVC BRASIL": ["CVC"],
    "AMBEV S/A": ["AMBEV"], "KLABIN S/A": ["KLABIN"], "SUZANO S.A.": ["SUZANO"], "CYRELA REALT": ["CYRELA"], "JHSF PART": ["JHSF"],
    "YDUQS PART": ["YDUQS"], "COGNA ON": ["COGNA"], "IGUATEMI S.A": ["IGUATEMI"], "VIVARA S.A.": ["VIVARA"], "RUMO S.A.": ["RUMO"],
    "GERDAU MET": ["METALURGICA GERDAU"], "SMART FIT": ["SMARTFIT"], "OUROFINO S/A": ["OUROFINO", "OURO FINO"],
    "CURY S/A": ["CURY"], "DOTZ SA": ["DOTZ"], "PETRORECSA": ["PETRORECONCAVO"], "SLC AGRICOLA": ["SLC"],
}


def _sem_acento(t):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))


def _texto(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _quando(s):
    s = (s or "").strip()
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        try:
            d = parsedate_to_datetime(s)
        except (TypeError, ValueError):
            d = datetime.strptime(s, "%d/%m/%Y %H:%M:%S").replace(tzinfo=FUSO_BR)
    if d.tzinfo is None:
        d = d.replace(tzinfo=FUSO_BR)
    return d.astimezone(FUSO_BR).isoformat(timespec="minutes")


def ler_feed(fonte, url, tipo="oficial", categoria="economia"):
    """RSS 2.0, RSS 1.0 (RDF) ou Atom, lidos com expressões regulares (os formatos variam entre os sites)."""
    xml = requests.get(url, headers=CABECALHO, timeout=60).text
    itens = []
    for bloco in re.findall(r"<(?:item|entry)\b.*?</(?:item|entry)>", xml, re.S):
        titulo = re.search(r"<title[^>]*>(.*?)</title>", bloco, re.S)
        link = re.search(r"<link[^>]*href=\"([^\"]+)\"", bloco) or re.search(r"<link>(.*?)</link>", bloco, re.S)
        data = re.search(r"<(pubDate|updated|dc:date|published)>(.*?)</\1>", bloco, re.S)
        if not (titulo and link and data):
            continue
        titulo = _texto(re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", titulo.group(1), flags=re.S))
        endereco = _texto(re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", link.group(1), flags=re.S))
        if "*http" in endereco:  # links de redirecionamento (Folha): fica o endereço final
            endereco = endereco[endereco.index("*http") + 1:]
        # o feed da CVM mistura pastas de anos antigos com as notícias
        if re.search(r"/noticias/(\d{4}(-\d)?|anexos)$", endereco) or len(titulo) < 12:
            continue
        cat = categoria_pela_url(endereco, categoria) if categoria == "url" else categoria
        if cat is None:
            continue
        itens.append({"data": _quando(data.group(2)), "titulo": titulo, "link": endereco, "fonte": fonte, "tipo": tipo, "categoria": cat})
    return itens


def ler_ibge():
    dados = requests.get(URL_IBGE, headers=CABECALHO, timeout=60).json()
    return [{"data": _quando(i["data_publicacao"]), "titulo": _texto(i["titulo"]), "link": i["link"], "fonte": "IBGE", "tipo": "oficial",
             "categoria": "economia"}
            for i in dados.get("items", [])]


def _apelidos():
    """(id, [(padrão, ambíguo)]) de cada empresa do universo, para ligar manchetes às empresas."""
    arq = DIR_DADOS_SITE / "mercado.json"
    if not arq.exists():
        return []
    saida = []
    for e in json.loads(arq.read_text(encoding="utf-8"))["empresas"]:
        nome = _sem_acento((e.get("nome_pregao") or "").upper().strip())
        limpo = " ".join(t for t in nome.split() if t not in SUFIXOS)
        termos = {limpo, *APELIDOS_EXTRAS.get(nome, [])}
        primeiro = limpo.split()[0] if limpo else ""
        if len(primeiro) >= 4 and primeiro not in GENERICOS and not primeiro.isdigit():
            termos.add(primeiro)
        termos = {t for t in termos if len(t) >= 3 and t not in GENERICOS}
        regras = [(re.compile(r"(?<![\w])" + re.escape(t) + r"(?![\w])", re.I), t in AMBIGUOS) for t in termos]
        # ticker: sempre vale (ex.: PETR4, VALE3)
        regras += [(re.compile(r"" + re.escape(t) + r""), False) for t in {*(e.get("cotacoes") or {}), e["id"]}]
        saida.append((e["id"], regras))
    return saida


def _cita(titulo, regras):
    t = _sem_acento(titulo)
    for rx, ambiguo in regras:
        for m in rx.finditer(t):
            achado = m.group(0)
            if achado.isupper() and len(achado) > 1:
                return True
            if achado[0].isupper() and not (ambiguo and m.start() == 0):
                return True
    return False


def _anteriores(nome):
    """Manchetes já guardadas: arquivo local e o publicado no site (a rodada anterior pode ter sido a do meio do dia)."""
    import os
    itens = []
    arq = DIR_DADOS_SITE / nome
    if arq.exists():
        try:
            itens += json.loads(arq.read_text(encoding="utf-8")).get("itens", [])
        except ValueError:
            pass
    dono, _, repo = os.environ.get("GITHUB_REPOSITORY", "fredperin/screeening-cvm").partition("/")
    try:
        r = requests.get(f"https://{dono}.github.io/{repo}/dados/{nome}", headers=CABECALHO, timeout=30)
        if r.ok:
            itens += r.json().get("itens", [])
    except (requests.RequestException, ValueError):
        pass
    # só manchetes no formato atual (com editoria)
    return [i for i in itens if i.get("categoria") and i.get("link") and i.get("data")]


def gerar():
    hoje = date.today()
    itens, falhas = [], []
    for tipo, feeds in (("oficial", FEEDS), ("mercado", FEEDS_MERCADO)):
        for fonte, url, categoria in feeds:
            try:
                itens += ler_feed(fonte, url.format(ano=hoje.year), tipo, categoria)
            except Exception as e:
                falhas.append(f"{fonte} ({categoria}): {e!r}"[:200])
    try:
        itens += ler_ibge()
    except Exception as e:
        falhas.append(f"IBGE: {e!r}"[:200])

    novas = len(itens)
    antigas = _anteriores("noticias.json") + _anteriores("noticias_empresas.json")
    apelidos = _apelidos()

    def marcar(i):
        # nomes só valem com inicial maiúscula (evita "vale a pena"); os ambíguos, também não no começo da manchete
        i["empresas"] = [id_ for id_, regras in apelidos if _cita(i["titulo"], regras)]
        # manchete de economia sobre uma empresa da lista vai para empresas; a editoria de origem fica guardada
        if i["empresas"] and i["categoria_origem"] == "economia":
            i["categoria"] = "empresas"
        else:
            i["categoria"] = i["categoria_origem"]
        return i

    # a coleta nova vem por último: vale a versão mais recente de cada link
    unicos = {}
    for i in antigas + itens:
        i = dict(i)
        i.setdefault("categoria_origem", i["categoria"])
        unicos[i["link"]] = marcar(i)
    todos = sorted(unicos.values(), key=lambda i: i["data"], reverse=True)

    limites = {"oficial": (hoje - timedelta(days=DIAS)).isoformat(), "mercado": (hoje - timedelta(days=DIAS_MERCADO)).isoformat()}
    itens = [i for i in todos if i["data"][:10] >= limites[i["tipo"]]][:MAXIMO]
    limite_emp = (hoje - timedelta(days=DIAS_EMPRESAS)).isoformat()
    das_empresas = [i for i in todos if i["empresas"] and i["data"][:10] >= limite_emp][:MAXIMO_EMPRESAS]
    agora = datetime.now(FUSO_BR).isoformat(timespec="minutes")
    (DIR_DADOS_SITE / "noticias.json").write_text(json.dumps(
        {"gerado_em": agora, "itens": itens, "falhas": falhas}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (DIR_DADOS_SITE / "noticias_empresas.json").write_text(json.dumps(
        {"gerado_em": agora, "dias": DIAS_EMPRESAS, "itens": das_empresas}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    por_fonte, por_cat = {}, {}
    for i in itens:
        por_fonte[i["fonte"]] = por_fonte.get(i["fonte"], 0) + 1
        por_cat[i["categoria"]] = por_cat.get(i["categoria"], 0) + 1
    print(f"✅ notícias: {novas} coletadas agora; {len(itens)} no ar {por_cat} {por_fonte}; "
          f"{len(das_empresas)} ligadas a empresas ({DIAS_EMPRESAS} dias); falhas: {falhas or 'nenhuma'}")
    if len(falhas) == len(FEEDS) + len(FEEDS_MERCADO) + 1:
        raise RuntimeError("nenhuma fonte de notícias respondeu")
    return len(itens)


if __name__ == "__main__":
    gerar()
