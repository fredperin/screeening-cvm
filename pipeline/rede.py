"""
Cliente de internet único do pipeline: todas as consultas feitas com `requests` (de qualquer módulo) passam
por aqui, para nenhuma fonte nos barrar por excesso.

- Ritmo por servidor: intervalo mínimo entre consultas ao mesmo endereço (RITMO), respeitado também entre
  consultas em paralelo. Se o servidor recusar (HTTP 429 ou 503), o intervalo daquele servidor dobra até o
  fim da execução (o ritmo seguro se ajusta sozinho).
- Recusa: espera o tempo que o servidor pede (cabeçalho Retry-After) ou 30 s e tenta mais uma vez; fontes
  que pioram quando se insiste (SEM_NOVA_TENTATIVA) devolvem a recusa na hora para o módulo decidir.
- Conexão reaproveitada (keep-alive) nas chamadas requests.get/post, cada uma com sua sessão (cookies isolados,
  como antes).
- Contagem interna por servidor (consultas, recusas e recusas não resolvidas) em data/pipeline/consultas.json,
  lida pelo monitor: só vira alerta se uma fonte terminar recusando.

Ativado em pipeline/__init__.py. O Yahoo (yfinance) usa outra biblioteca e não passa por aqui.
"""

import atexit
import json
import threading
import time
from datetime import date
from urllib.parse import urlsplit

RITMO = {  # segundos entre consultas ao mesmo servidor
    "api.bcb.gov.br": 0.1, "olinda.bcb.gov.br": 0.2, "dadosabertos.bcb.gov.br": 0.5, "www3.bcb.gov.br": 0.2,
    "cotacao.b3.com.br": 0.2, "sistemaswebb3-listados.b3.com.br": 0.2, "www.b3.com.br": 0.5, "arquivos.b3.com.br": 0.5,
    "api-comexstat.mdic.gov.br": 5, "www.tesourotransparente.gov.br": 2, "www.tesourodireto.com.br": 1,
    "dados.cvm.gov.br": 0.2, "www.rad.cvm.gov.br": 0.3,
    "data.sec.gov": 0.11, "www.sec.gov": 0.11,  # SEC: até 10 por segundo
    "api.stlouisfed.org": 0.5,                  # FRED: até 120 por minuto
    "api.bls.gov": 1, "sdmx.oecd.org": 3, "www.imf.org": 1, "api.imf.org": 1, "api.worldbank.org": 0.3,
    "ec.europa.eu": 0.3, "data-api.ecb.europa.eu": 0.3, "markets.newyorkfed.org": 0.3, "home.treasury.gov": 0.5,
    "servicodados.ibge.gov.br": 0.3, "apisidra.ibge.gov.br": 0.3,
}
RITMO_PADRAO = 0.1
SEM_NOVA_TENTATIVA = {"api-comexstat.mdic.gov.br"}  # o Comex Stat só piora quando se insiste
ESPERA_PADRAO, ESPERA_MAXIMA = 30, 120  # segundos
RITMO_MAXIMO = 10

_trava = threading.Lock()
_proxima = {}         # servidor -> momento a partir do qual a próxima consulta pode sair
_ritmo_atual = {}     # servidor -> intervalo em uso (dobra a cada recusa)
_contagem = {}        # servidor -> {"consultas", "recusas", "recusas_finais", "espera_s"}
_instalado = False


def _contar(servidor, campo, n=1):
    with _trava:
        c = _contagem.setdefault(servidor, {"consultas": 0, "recusas": 0, "recusas_finais": 0, "espera_s": 0})
        c[campo] += n


def _esperar_vez(servidor):
    with _trava:
        agora = time.monotonic()
        intervalo = _ritmo_atual.get(servidor, RITMO.get(servidor, RITMO_PADRAO))
        sair_em = max(agora, _proxima.get(servidor, 0))
        _proxima[servidor] = sair_em + intervalo
    if sair_em > agora:
        time.sleep(sair_em - agora)


def _retry_after(resposta):
    valor = (resposta.headers.get("Retry-After") or "").strip()
    return int(valor) if valor.isdigit() else None


def instalar():
    """Liga o cliente único para todo o processo (idempotente)."""
    global _instalado
    if _instalado:
        return
    import requests
    import requests.api

    original = requests.Session.request

    def request(self, method, url, *args, **kwargs):
        servidor = urlsplit(url).hostname or ""
        for tentativa in range(2):
            _esperar_vez(servidor)
            r = original(self, method, url, *args, **kwargs)
            _contar(servidor, "consultas")
            if r.status_code not in (429, 503):
                return r
            _contar(servidor, "recusas")
            with _trava:
                base = _ritmo_atual.get(servidor, RITMO.get(servidor, RITMO_PADRAO))
                _ritmo_atual[servidor] = min(max(base * 2, 1.0), RITMO_MAXIMO)
            espera = _retry_after(r) or ESPERA_PADRAO
            if tentativa == 1 or servidor in SEM_NOVA_TENTATIVA or espera > ESPERA_MAXIMA:
                _contar(servidor, "recusas_finais")
                return r
            r.close()
            _contar(servidor, "espera_s", espera)
            time.sleep(espera)
        return r

    # Uma sessão nova por chamada (cookies e cabeçalhos isolados, como no requests.get original), mas com o
    # mesmo conjunto de conexões: a conexão com cada servidor é reaproveitada entre as chamadas
    conexoes = requests.adapters.HTTPAdapter(pool_connections=32, pool_maxsize=16)

    def api_request(method, url, **kwargs):
        s = requests.Session()
        s.mount("https://", conexoes)
        s.mount("http://", conexoes)
        return s.request(method=method, url=url, **kwargs)  # sem fechar a sessão: fecharia as conexões em comum

    requests.Session.request = request
    requests.api.request = api_request
    atexit.register(gravar)
    _instalado = True


def contagem():
    with _trava:
        return {s: dict(c) for s, c in _contagem.items()}


def gravar():
    """Soma a contagem desta execução à do dia em data/pipeline/consultas.json (guarda os últimos 14 dias)."""
    if not _contagem:
        return
    from pipeline import DIR_INTERMEDIARIO
    arq = DIR_INTERMEDIARIO / "consultas.json"
    try:
        dados = json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dados = {}
    dia = dados.setdefault(date.today().isoformat(), {})
    for servidor, c in contagem().items():
        acumulado = dia.setdefault(servidor, {"consultas": 0, "recusas": 0, "recusas_finais": 0, "espera_s": 0})
        for k, v in c.items():
            acumulado[k] = acumulado.get(k, 0) + v
    dados = {k: dados[k] for k in sorted(dados)[-14:]}
    try:
        arq.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass
