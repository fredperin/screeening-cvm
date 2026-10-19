"""
Curvas DI x Pré e DI x IPCA da B3 (arquivo diário "Taxas de Mercado para Swaps",
pesquisa por pregão) em 5 datas -> site/dados/curva_di.json

Fonte pública de fim de dia da B3; o site cita a fonte.
"""

import io
import json
import re
import zipfile
from datetime import date, timedelta

import requests

from config.config import RAW_DIR
from pipeline import DIR_DADOS_SITE

URL = "https://www.b3.com.br/pesquisapregao/download?filelist=TS{:%y%m%d}.ex_"
DIR_CACHE = RAW_DIR / "b3_taxaswap"
DATAS_REFERENCIA = {"hoje": 0, "1 semana": 7, "1 mês": 30, "6 meses": 182, "1 ano": 365}
CURVAS = {"PRE": "pre", "DIC": "ipca"}
REGISTRO = re.compile(r"(\d{6})(\d{3})(\d{2})(\d{8})(.{2})(.{5})(.{15})(\d{5})(\d{5})([+-])(\d{14})([FM])(\d{5})")


def _baixar_dia(dia):
    """Conteúdo do TaxaSwap.txt do pregão `dia`, ou None se não houve pregão/arquivo."""
    DIR_CACHE.mkdir(parents=True, exist_ok=True)
    cache = DIR_CACHE / f"TaxaSwap_{dia:%Y%m%d}.txt"
    if cache.exists():
        return cache.read_text(encoding="latin1")
    r = requests.get(URL.format(dia), headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    if r.status_code != 200 or not r.content.startswith(b"PK"):
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(r.content)) as externo:
            if not externo.namelist():  # a B3 publica o ZIP do dia vazio antes de sair o arquivo: usa o pregão anterior
                return None
            interno = externo.read(externo.namelist()[0])
        with zipfile.ZipFile(io.BytesIO(interno)) as z:
            texto = z.read("TaxaSwap.txt").decode("latin1")
    except (zipfile.BadZipFile, KeyError):
        return None
    cache.write_text(texto, encoding="latin1")
    return texto


def _ultimo_pregao_ate(alvo, limite_dias=10):
    for i in range(limite_dias):
        dia = alvo - timedelta(days=i)
        if dia.weekday() >= 5:
            continue
        texto = _baixar_dia(dia)
        if texto:
            return dia, texto
    return None, None


def _parse(texto):
    curvas = {nome: [] for nome in CURVAS.values()}
    for r in REGISTRO.findall(texto):
        codigo = r[5].strip()
        if codigo not in CURVAS:
            continue
        dias_uteis = int(r[8])
        taxa = int(r[10]) / 1e7 * (-1 if r[9] == "-" else 1)
        curvas[CURVAS[codigo]].append({"dias_corridos": int(r[7]), "dias_uteis": dias_uteis,
                                       "anos": round(dias_uteis / 252, 4), "taxa": round(taxa, 4)})
    for pontos in curvas.values():
        pontos.sort(key=lambda p: p["dias_uteis"])
    return curvas


def gerar(hoje=None):
    hoje = hoje or date.today()
    ultimo, _ = _ultimo_pregao_ate(hoje)
    if ultimo is None:
        raise RuntimeError("Nenhum arquivo TaxaSwap da B3 nos últimos 10 dias")

    saida = {}
    for rotulo, dias in DATAS_REFERENCIA.items():
        dia, texto = _ultimo_pregao_ate(ultimo - timedelta(days=dias))
        if dia is None:
            print(f"⚠️ curva DI: sem arquivo da B3 perto de {rotulo}")
            continue
        saida[rotulo] = {"data": dia.isoformat(), **_parse(texto)}

    arquivo = DIR_DADOS_SITE / "curva_di.json"
    arquivo.write_text(json.dumps({"gerado_em": date.today().isoformat(), "fonte": "B3 — Taxas de Mercado para Swaps",
                                   "curvas": saida}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return arquivo


if __name__ == "__main__":
    caminho = gerar()
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    for rotulo, c in dados["curvas"].items():
        pre, ipca = c["pre"], c["ipca"]
        print(f"{rotulo:9s} {c['data']}  DIxPré {len(pre)} pts ({pre[0]['taxa']}% → {pre[-1]['taxa']}% em {pre[-1]['anos']}a)"
              f"  DIxIPCA {len(ipca)} pts")
    print(caminho.stat().st_size // 1024, "KB")
