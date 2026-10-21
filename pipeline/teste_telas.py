"""
Teste automático das telas do site (sem IA, roda no GitHub Actions depois da atualização).

Abre o site gerado (pasta site/) num navegador sem tela (Playwright/Chromium) e percorre cada seção e aba:
- erros de JavaScript na página e a mensagem "Não foi possível carregar";
- gráficos sem desenho ou sem nenhum dado (todas as séries vazias);
- tabelas vazias onde deveria haver linhas.
Também confere, por amostra, se os links para documentos oficiais (CVM, SEC) respondem.

Saída: data/pipeline/teste_telas.json (lido pelo monitor, que põe os problemas nas Observações).
Com --capturas PASTA, salva uma imagem de cada tela (usada pelo agente revisor visual); com --site URL, testa o site
publicado em vez da pasta local (ex.: --site https://fredperin.github.io/screeening-cvm/).
Uso: py -m pipeline.teste_telas [--capturas PASTA] [--site URL]
"""

import functools
import http.server
import json
import random
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from pipeline import DIR_DADOS_SITE, DIR_INTERMEDIARIO, RAIZ

ARQ = DIR_INTERMEDIARIO / "teste_telas.json"
FUSO_BR = timezone(timedelta(hours=-3))
PORTA = 8799

# (rota, botões de abas internas a percorrer: seletor CSS dos botões)
ROTAS = [
    ("#/on", None), ("#/on/noticias", None),
    *[(f"#/on/macro/{s}", None) for s in ("atividade", "inflacao", "expectativas", "monetaria", "fiscal", "cambio", "externo")],
    ("#/on/macro/credito", "#sub-credito button"),
    ("#/on/juros", None),
    *[(f"#/on/empresas/{a}", None) for a in ("noticias", "fatos", "tabela", "financeiras")],
    ("#/on/empresa/VALE3", "#abas-empresa button"), ("#/on/empresa/WEGE3", "#abas-empresa button"),
    ("#/on/banco/c0080099", "#abas-banco button"), ("#/on/downloads", None),
    ("#/off", None), ("#/off/noticias", None),
    ("#/off/macro/global", "#ind-global button"), ("#/off/macro/eua", "#sub-pais button"), ("#/off/macro/euro", "#sub-pais button"),
    ("#/off/macro/china", "#sub-pais button"), ("#/off/macro/mercados", "#sub-mercados button"),
    ("#/off/juros", None), ("#/off/empresas", None), ("#/off/empresa/AAPL", "#abas-empresa-mundo button"), ("#/off/empresa/MSFT", "#abas-empresa-mundo button"),
    ("#/cons", None), ("#/cons/atividade", None), ("#/cons/inflacao", None), ("#/cons/juros", None),
    ("#/status", None),
]

# Inspeção feita dentro da página: painéis com gráfico sem desenho/sem dados e tabelas vazias
INSPECAO = """() => {
  const res = { erro: null, paineis: 0, problemas: [] };
  const err = document.querySelector('#app .erro');
  if (err) res.erro = err.textContent.slice(0, 200);
  document.querySelectorAll('#app .painel').forEach((p) => {
    res.paineis++;
    const titulo = (p.querySelector('h2') || {}).textContent || '(sem título)';
    const g = p.querySelector('.grafico');
    if (g) {
      const inst = window.echarts && echarts.getInstanceByDom(g);
      if (!inst) { if (!g.textContent.trim()) res.problemas.push(`gráfico não desenhado: ${titulo.slice(0, 70)}`); return; }
      const series = (inst.getOption().series || []);
      const comDado = series.filter((s) => (s.data || []).some((x) => x != null && (Array.isArray(x) ? x[1] != null : true)));
      if (!comDado.length) res.problemas.push(`gráfico sem dados: ${titulo.slice(0, 70)}`);
    }
  });
  return res;
}"""


def _servidor():
    pasta = str(RAIZ / "site")
    class Silencioso(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a, **k):
            pass
    manipulador = functools.partial(Silencioso, directory=pasta)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORTA), manipulador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def testar_telas(capturas=None, site=None):
    from playwright.sync_api import sync_playwright

    srv = None if site else _servidor()
    base = site.rstrip("/") + "/index.html" if site else f"http://127.0.0.1:{PORTA}/index.html"
    telas, problemas = [], []
    try:
        with sync_playwright() as p:
            nav = p.chromium.launch()
            pag = nav.new_page(viewport={"width": 1366, "height": 900})
            erros_js = []
            pag.on("pageerror", lambda e: erros_js.append(str(e)[:200]))
            pag.goto(base, wait_until="load")
            for rota, botoes in ROTAS:
                pag.evaluate(f"location.hash = '{rota}'")
                pag.wait_for_timeout(2500)
                visitas = [(rota, None)]
                if botoes:
                    n = pag.locator(botoes).count()
                    visitas += [(rota, i) for i in range(n)]
                for _, i in visitas:
                    nome = rota
                    if i is not None:
                        b = pag.locator(botoes).nth(i)
                        nome = f"{rota} › {b.inner_text().strip()[:40]}"
                        try:
                            b.click(timeout=5000)
                        except Exception:  # noqa: BLE001
                            problemas.append(f"{nome}: botão não clicável")
                            continue
                        pag.wait_for_timeout(1500)
                    antes = len(erros_js)
                    r = pag.evaluate(INSPECAO)
                    novos = erros_js[antes:]
                    tela = {"tela": nome, "paineis": r["paineis"], "problemas": r["problemas"] + [f"erro de JavaScript: {e}" for e in novos]}
                    if r["erro"]:
                        tela["problemas"].append(f"página não carregou: {r['erro']}")
                    telas.append(tela)
                    problemas += [f"{nome}: {x}" for x in tela["problemas"]]
                    if capturas:
                        arq = Path(capturas) / (nome.replace("#/", "").replace("/", "_").replace(" › ", "__").replace(" ", "-")[:90] + ".png")
                        pag.screenshot(path=str(arq), full_page=True)
            nav.close()
    finally:
        if srv:
            srv.shutdown()
    return telas, problemas


def testar_links(amostra=12):
    """Amostra de links para documentos oficiais (CVM e SEC) usados nas páginas das empresas."""
    links = []
    for arq in random.sample(sorted((DIR_DADOS_SITE / "eventos").glob("*.json")), k=min(4, len(list((DIR_DADOS_SITE / "eventos").glob("*.json"))))):
        links += [e["link"] for e in json.loads(arq.read_text(encoding="utf-8")).get("eventos", [])[:2] if e.get("link")]
    for arq in random.sample(sorted((DIR_DADOS_SITE / "mundo_empresas").glob("*.json")), k=min(4, len(list((DIR_DADOS_SITE / "mundo_empresas").glob("*.json"))))):
        links += [d["link"] for d in json.loads(arq.read_text(encoding="utf-8")).get("documentos", [])[:2] if d.get("link")]
    import os
    falhas = []
    sec_ua = os.environ.get("SEC_USER_AGENT")
    links = [u for u in links if sec_ua or "sec.gov" not in u]  # a SEC recusa consultas sem identificação
    for url in links[:amostra]:
        cab = {"User-Agent": sec_ua} if "sec.gov" in url else {"User-Agent": "Mozilla/5.0"}
        try:
            r = requests.get(url, headers=cab, timeout=30, stream=True)
            if r.status_code >= 400:
                falhas.append(f"{r.status_code} {url.split('//', 1)[-1][:90]}")
        except requests.RequestException as e:
            falhas.append(f"sem resposta {url.split('//', 1)[-1][:90]} ({type(e).__name__})")
        time.sleep(0.3)
    return len(links[:amostra]), falhas


def main():
    capturas = sys.argv[sys.argv.index("--capturas") + 1] if "--capturas" in sys.argv else None
    site = sys.argv[sys.argv.index("--site") + 1] if "--site" in sys.argv else None
    if capturas:
        Path(capturas).mkdir(parents=True, exist_ok=True)
    inicio = time.time()
    telas, problemas = testar_telas(capturas, site)
    n_links, falhas_links = testar_links()
    if site:  # teste do site publicado (revisor visual): não sobrescreve o resultado da atualização
        global ARQ
        ARQ = ARQ.with_name("teste_telas_publicado.json")
    resultado = {"verificado_em": datetime.now(FUSO_BR).isoformat(timespec="minutes"), "telas": len(telas),
                 "problemas": problemas, "links_testados": n_links, "links_com_falha": falhas_links,
                 "segundos": round(time.time() - inicio), "detalhe": telas}
    ARQ.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ teste das telas: {len(telas)} telas, {len(problemas)} problema(s); links: {n_links} testados, {len(falhas_links)} com falha ({resultado['segundos']} s)")
    for x in problemas[:40] + falhas_links:
        print("   ⚠️", x)


if __name__ == "__main__":
    main()
