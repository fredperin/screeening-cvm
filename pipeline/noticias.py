"""
Manchetes de fontes oficiais e públicas (só título, data e link para a matéria original).

Onshore, dois tipos:
- oficiais: Banco Central (notícias e comunicados do Copom), IBGE (Agência de Notícias),
  CVM e Agência Brasil (editoria de economia);
- mercado: RSS públicos de Valor Econômico, Folha (Mercado), Estadão (Economia), Brazil Journal
  e InfoMoney — só a manchete com link para o jornal (o texto continua no site de cada um).
As manchetes que citam uma empresa do universo (pelo ticker ou pelo nome de pregão da B3)
ficam ligadas a ela.

Saída: site/dados/noticias.json. Uso: py -m pipeline.noticias
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
MAXIMO = 700
FUSO_BR = timezone(timedelta(hours=-3))

FEEDS = {
    "Banco Central": "https://www.bcb.gov.br/api/feed/sitebcb/sitefeeds/noticias",
    "Banco Central — Copom": "https://www.bcb.gov.br/api/feed/sitebcb/sitefeeds/comunicadoscopom",
    "CVM": "https://www.gov.br/cvm/pt-br/assuntos/noticias/{ano}/RSS",
    "Agência Brasil": "https://agenciabrasil.ebc.com.br/rss/economia/feed.xml",
}
FEEDS_MERCADO = {
    "Valor Econômico": "https://pox.globo.com/rss/valor/",
    "Folha": "https://feeds.folha.uol.com.br/mercado/rss091.xml",
    "Estadão": "https://www.estadao.com.br/arc/outboundfeeds/feeds/rss/sections/economia/",
    "Brazil Journal": "https://braziljournal.com/feed/",
    "InfoMoney": "https://www.infomoney.com.br/feed/",
}
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


def ler_feed(fonte, url, tipo="oficial"):
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
        itens.append({"data": _quando(data.group(2)), "titulo": titulo, "link": endereco, "fonte": fonte, "tipo": tipo})
    return itens


def ler_ibge():
    dados = requests.get(URL_IBGE, headers=CABECALHO, timeout=60).json()
    return [{"data": _quando(i["data_publicacao"]), "titulo": _texto(i["titulo"]), "link": i["link"], "fonte": "IBGE", "tipo": "oficial"}
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


def gerar():
    hoje = date.today()
    itens, falhas = [], []
    for fonte, url in FEEDS.items():
        try:
            itens += ler_feed(fonte, url.format(ano=hoje.year))
        except Exception as e:
            falhas.append(f"{fonte}: {e!r}"[:200])
    try:
        itens += ler_ibge()
    except Exception as e:
        falhas.append(f"IBGE: {e!r}"[:200])
    for fonte, url in FEEDS_MERCADO.items():
        try:
            itens += ler_feed(fonte, url, "mercado")
        except Exception as e:
            falhas.append(f"{fonte}: {e!r}"[:200])

    limites = {"oficial": (hoje - timedelta(days=DIAS)).isoformat(), "mercado": (hoje - timedelta(days=DIAS_MERCADO)).isoformat()}
    unicos = {i["link"]: i for i in itens if i["data"][:10] >= limites[i["tipo"]]}
    itens = sorted(unicos.values(), key=lambda i: i["data"], reverse=True)[:MAXIMO]
    apelidos = _apelidos()
    for i in itens:
        # nomes só valem com inicial maiúscula (evita "vale a pena"); os ambíguos, também não no começo da manchete
        i["empresas"] = [id_ for id_, regras in apelidos if _cita(i["titulo"], regras)]
    (DIR_DADOS_SITE / "noticias.json").write_text(json.dumps(
        {"gerado_em": datetime.now(FUSO_BR).isoformat(timespec="minutes"), "itens": itens, "falhas": falhas},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    por_fonte = {}
    for i in itens:
        por_fonte[i["fonte"]] = por_fonte.get(i["fonte"], 0) + 1
    print(f"✅ notícias: {len(itens)} manchetes {por_fonte}; falhas: {falhas or 'nenhuma'}")
    if len(falhas) == len(FEEDS) + len(FEEDS_MERCADO) + 1:
        raise RuntimeError("nenhuma fonte de notícias respondeu")
    return len(itens)


if __name__ == "__main__":
    gerar()
