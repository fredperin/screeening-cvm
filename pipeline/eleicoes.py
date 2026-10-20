"""
Eleições 2026 — Presidente (resultado oficial do TSE, arquivos públicos de divulgação de resultados).

1º turno (04/10/2026) e 2º turno (25/10/2026): votos e % de cada candidato no Brasil, comparecimento,
abstenção, brancos e nulos, e o mais votado em cada estado. Durante a apuração o arquivo do TSE é
atualizado; o site mostra o % de seções apuradas.

Saída: site/dados/eleicoes.json. Uso: py -m pipeline.eleicoes
"""

import json
from datetime import datetime, timedelta, timezone

import requests

from pipeline import DIR_DADOS_SITE

CABECALHO = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"}
FUSO_BR = timezone(timedelta(hours=-3))
URL = "https://resultados.tse.jus.br/oficial/ele2026/{eleicao}/dados/{uf}/{uf}-c0001-e{eleicao:06d}-u.json"
TURNOS = [(1, 6257, "2026-10-04"), (2, 6258, "2026-10-25")]  # códigos do TSE (config ele-c.json): eleição federal 2026
UFS = ["ac", "al", "am", "ap", "ba", "ce", "df", "es", "go", "ma", "mg", "ms", "mt", "pa", "pb", "pe", "pi", "pr", "rj", "rn",
       "ro", "rr", "rs", "sc", "se", "sp", "to"]


def _num(texto):
    return float(str(texto).replace(".", "").replace(",", ".")) if texto not in (None, "") else None


def _baixar(eleicao, uf):
    r = requests.get(URL.format(eleicao=eleicao, uf=uf), headers=CABECALHO, timeout=60)
    r.raise_for_status()
    return r.json()


def _candidatos(d):
    saida = []
    for agr in d["carg"][0]["agr"]:
        for par in agr["par"]:
            for c in par["cand"]:
                saida.append({"nome": c["nmu"], "numero": c["n"], "partido": par["sg"],
                              "coligacao": agr["nm"] if agr.get("tp") == "c" else None, "coligacao_partidos": agr.get("com"),
                              "vice": (c.get("vs") or [{}])[0].get("nmu"), "votos": int(c["vap"] or 0), "pct": _num(c["pvap"]),
                              "situacao": c.get("st") or ""})
    return sorted(saida, key=lambda c: c["votos"], reverse=True)


def turno(numero, eleicao, data):
    d = _baixar(eleicao, "br")
    apurado = _num(d["s"]["pst"])
    resumo = {
        "turno": numero, "data": data, "atualizado_tse": f"{d['dg']} {d['hg']}", "apurado_pct": apurado,
        "eleitores": int(d["e"]["te"]), "comparecimento_pct": _num(d["e"]["pc"]), "abstencao_pct": _num(d["e"]["pa"]),
        "votos_validos": int(d["v"]["vv"] or 0), "brancos_pct": _num(d["v"]["pvb"]), "nulos_pct": _num(d["v"]["ptvn"]),
        "candidatos": _candidatos(d), "por_uf": {},
    }
    if apurado and apurado > 0:
        for uf in UFS:
            cands = _candidatos(_baixar(eleicao, uf))
            resumo["por_uf"][uf.upper()] = [{"nome": c["nome"], "pct": c["pct"]} for c in cands[:2]]
    return resumo


def gerar():
    turnos = [turno(*t) for t in TURNOS]
    (DIR_DADOS_SITE / "eleicoes.json").write_text(json.dumps({
        "gerado_em": datetime.now(FUSO_BR).isoformat(timespec="minutes"), "cargo": "Presidente", "turnos": turnos,
        "fonte": "TSE — Divulgação de Resultados (resultados.tse.jus.br)"}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for t in turnos:
        print(f"✅ eleições {t['turno']}º turno: {t['apurado_pct']}% apurado;",
              ", ".join(f"{c['nome']} {c['pct']}%" for c in t["candidatos"][:3]))
    return turnos


if __name__ == "__main__":
    gerar()
