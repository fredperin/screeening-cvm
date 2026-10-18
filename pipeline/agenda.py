"""
Agenda macroeconômica: próximas divulgações e reuniões relevantes, das fontes oficiais.

- Banco Central (calendário do site): reuniões do Copom, atas, Relatório de Política
  Monetária, boletim Focus e IBC-Br;
- IBGE (API de calendário): IPCA, IPCA-15, PIB trimestral, PNAD Contínua (desemprego),
  produção industrial, varejo e serviços;
- FGV (página de calendário de divulgação): IGP-M.

Saída: site/dados/agenda.json. Uso: py -m pipeline.agenda
"""

import html
import json
import re
from datetime import date, datetime, timedelta
from urllib.parse import quote

import requests

from pipeline import DIR_DADOS_SITE

CABECALHO = {"User-Agent": "Mozilla/5.0"}
HORIZONTE_DIAS = 400

URL_BCB = "https://www.bcb.gov.br/api/servico/sitebcb/calendario?inicioAgenda=%27{ini}%27&fimAgenda=%27{fim}%27&lista={lista}"
LISTAS_BCB = {
    "Reuniões do Copom": ("copom", "Copom — decisão da Selic"),
    "Atas e Comunicados do Copom": ("copom", None),
    "Relatório de Política Monetária": ("bc", "Relatório de Política Monetária"),
    "Focus": ("bc", "Boletim Focus"),
    "Índice de atividade econômica (IBC-Br)": ("atividade", "IBC-Br (prévia do PIB)"),
}

URL_IBGE = "https://servicodados.ibge.gov.br/api/v3/calendario/?qtd=500&de={ini}&ate={fim}"
PRODUTOS_IBGE = {
    "Índice Nacional de Preços ao Consumidor Amplo": ("inflacao", "IPCA"),
    "Índice Nacional de Preços ao Consumidor Amplo 15": ("inflacao", "IPCA-15"),
    "Sistema de Contas Nacionais Trimestrais": ("atividade", "PIB trimestral"),
    "Divulgação mensal#pnadc1": ("trabalho", "PNAD Contínua (desemprego)"),
    "PIM-PF Brasil#pimpf1": ("atividade", "Produção industrial (PIM)"),
    "Pesquisa Mensal de Comércio": ("atividade", "Vendas no varejo (PMC)"),
    "Pesquisa Mensal de Serviços": ("atividade", "Volume de serviços (PMS)"),
}

URL_FGV = "https://portalibre.fgv.br/calendario-de-divulgacao"


def _limpar(texto):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", texto or ""))).strip()


def eventos_bcb(hoje, fim):
    saida = []
    for lista, (categoria, titulo) in LISTAS_BCB.items():
        url = URL_BCB.format(ini=hoje.isoformat(), fim=fim.isoformat(), lista=quote(lista))
        dados = requests.get(url, headers=CABECALHO, timeout=60).json().get("conteudo", [])
        datas = sorted({x["dataEvento"][:10] for x in dados})
        if lista == "Reuniões do Copom":
            # Reunião de dois dias: a decisão sai no segundo, à noite
            dias = [date.fromisoformat(d) for d in datas]
            decisoes = [d for d in dias if d + timedelta(days=-1) in dias] or dias
            saida += [{"data": d.isoformat(), "evento": titulo, "categoria": categoria, "fonte": "Banco Central",
                       "detalhe": "Reunião de 2 dias; o comunicado sai ao fim do segundo dia"} for d in decisoes]
            continue
        for x in dados:
            nome = titulo or _limpar(x.get("evento"))
            saida.append({"data": x["dataEvento"][:10], "evento": nome, "categoria": categoria, "fonte": "Banco Central",
                          "detalhe": _limpar(x.get("descricao"))[:140] or None})
    return saida


def eventos_ibge(hoje, fim):
    url = URL_IBGE.format(ini=hoje.strftime("%m-%d-%Y"), fim=fim.strftime("%m-%d-%Y"))
    itens = requests.get(url, timeout=60).json().get("items", [])
    saida = []
    for i in itens:
        if i.get("nome_produto") not in PRODUTOS_IBGE:
            continue
        categoria, nome = PRODUTOS_IBGE[i["nome_produto"]]
        quando = datetime.strptime(i["data_divulgacao"][:10], "%d/%m/%Y").date()
        saida.append({"data": quando.isoformat(), "evento": nome, "categoria": categoria, "fonte": "IBGE",
                      "detalhe": _limpar(i.get("titulo"))[:140] or None})
    return saida


def _sessao_fgv():
    """O servidor da FGV só aceita cifras que o OpenSSL atual rebaixou de nível; libera só para esse site."""
    import ssl
    from requests.adapters import HTTPAdapter

    class Adaptador(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            contexto = ssl.create_default_context()
            contexto.set_ciphers("DEFAULT@SECLEVEL=1")
            kwargs["ssl_context"] = contexto
            return super().init_poolmanager(*args, **kwargs)

    sessao = requests.Session()
    sessao.mount("https://portalibre.fgv.br", Adaptador())
    return sessao


def eventos_fgv(hoje):
    saida = []
    sessao = _sessao_fgv()
    for pagina in range(3):
        r = sessao.get(URL_FGV + (f"?page={pagina}" if pagina else ""), headers=CABECALHO, timeout=60)
        if r.status_code != 200:
            break
        linhas = [l.strip() for l in _limpar_html_em_linhas(r.text) if l.strip()]
        for k in range(len(linhas) - 2):
            if re.fullmatch(r"\d{2}/\d{2}/\d{4}", linhas[k]) and linhas[k + 2].startswith("IGP-M e"):
                quando = datetime.strptime(linhas[k], "%d/%m/%Y").date()
                if quando >= hoje:
                    saida.append({"data": quando.isoformat(), "evento": "IGP-M", "categoria": "inflacao",
                                  "fonte": "FGV", "detalhe": linhas[k + 2][:140]})
    return saida


def _limpar_html_em_linhas(texto):
    sem_script = re.sub(r"<script.*?</script>|<style.*?</style>", "", texto, flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", "\n", sem_script)).splitlines()


def gerar():
    hoje = date.today()
    fim = hoje + timedelta(days=HORIZONTE_DIAS)
    eventos, falhas = [], []
    for nome, funcao in (("Banco Central", lambda: eventos_bcb(hoje, fim)), ("IBGE", lambda: eventos_ibge(hoje, fim)),
                         ("FGV", lambda: eventos_fgv(hoje))):
        try:
            eventos += funcao()
        except Exception as e:
            falhas.append(f"{nome}: {e!r}"[:200])
    unicos = {(e["data"], e["evento"]): e for e in eventos if e["data"] >= hoje.isoformat()}
    eventos = sorted(unicos.values(), key=lambda e: (e["data"], e["evento"]))
    (DIR_DADOS_SITE / "agenda.json").write_text(json.dumps(
        {"gerado_em": hoje.isoformat(), "eventos": eventos, "falhas": falhas}, ensure_ascii=False,
        separators=(",", ":")), encoding="utf-8")
    print(f"✅ agenda: {len(eventos)} eventos; falhas: {falhas or 'nenhuma'}")
    if len(falhas) == 3:
        raise RuntimeError("nenhuma fonte da agenda respondeu")
    return len(eventos)


if __name__ == "__main__":
    gerar()
