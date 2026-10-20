"""
Eleições — Presidente (resultado oficial do TSE, arquivos públicos de divulgação de resultados).

Liga e desliga sozinha: o calendário de eleições do próprio TSE (config ele-c.json) diz se há eleição
federal no ano; a seção fica ativa de 1º de janeiro do ano eleitoral até DIAS_DEPOIS dias depois da última
votação (2º turno, ou o 1º se ninguém precisar de 2º turno). Fora disso, o arquivo sai com "ativo": false
e o site esconde a aba.

Por turno: votos e % de cada candidato no Brasil, comparecimento, abstenção, brancos e nulos e o mais
votado em cada estado; durante a apuração, o % de seções apuradas.

Saída: site/dados/eleicoes.json. Uso: py -m pipeline.eleicoes
"""

import json
from datetime import date, datetime, timedelta, timezone

import requests

from pipeline import DIR_DADOS_SITE

CABECALHO = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"}
FUSO_BR = timezone(timedelta(hours=-3))
URL_CONFIG = "https://resultados.tse.jus.br/oficial/comum/config/ele-c.json"
URL = "https://resultados.tse.jus.br/oficial/{ciclo}/{eleicao}/dados/{uf}/{uf}-c0001-e{eleicao:06d}-u.json"
DIAS_DEPOIS = 15
UFS = ["ac", "al", "am", "ap", "ba", "ce", "df", "es", "go", "ma", "mg", "ms", "mt", "pa", "pb", "pe", "pi", "pr", "rj", "rn",
       "ro", "rr", "rs", "sc", "se", "sp", "to"]


def _num(texto):
    return float(str(texto).replace(".", "").replace(",", ".")) if texto not in (None, "") else None


def _baixar(ciclo, eleicao, uf):
    r = requests.get(URL.format(ciclo=ciclo, eleicao=eleicao, uf=uf), headers=CABECALHO, timeout=60)
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


def eleicao_do_ano(ano):
    """Ciclo, códigos e datas da eleição presidencial do ano no calendário do TSE (None se não houver)."""
    config = requests.get(URL_CONFIG, headers=CABECALHO, timeout=60).json()
    for pleito in config.get("pl", []):
        if pleito.get("c") != f"ele{ano}":
            continue
        for e in pleito.get("e", []):
            cargos = [c for a in e.get("abr", []) for c in a.get("cp", [])]
            if e.get("t") == "1" and any(c.get("cd") == "1" for c in cargos):  # 1º turno com cargo de Presidente
                d1 = datetime.strptime(pleito["dt"], "%d/%m/%Y").date()
                d2 = date(ano, 10, 31)  # 2º turno: último domingo de outubro (Constituição, art. 77)
                d2 -= timedelta(days=(d2.weekday() + 1) % 7)
                return {"ciclo": pleito["c"], "turnos": [(1, int(e["cd"]), d1.isoformat()), (2, int(e["cdt2"]), d2.isoformat())]}
    return None


def turno(ciclo, numero, eleicao, data):
    d = _baixar(ciclo, eleicao, "br")
    apurado = _num(d["s"]["pst"])
    resumo = {
        "turno": numero, "data": data, "atualizado_tse": f"{d['dg']} {d['hg']}", "apurado_pct": apurado,
        "eleitores": int(d["e"]["te"]), "comparecimento_pct": _num(d["e"]["pc"]), "abstencao_pct": _num(d["e"]["pa"]),
        "votos_validos": int(d["v"]["vv"] or 0), "brancos_pct": _num(d["v"]["pvb"]), "nulos_pct": _num(d["v"]["ptvn"]),
        "candidatos": _candidatos(d), "por_uf": {},
    }
    if apurado and apurado > 0:
        for uf in UFS:
            cands = _candidatos(_baixar(ciclo, eleicao, uf))
            resumo["por_uf"][uf.upper()] = [{"nome": c["nome"], "pct": c["pct"]} for c in cands[:2]]
    return resumo


def gerar():
    hoje = date.today()
    agora = datetime.now(FUSO_BR).isoformat(timespec="minutes")
    arq = DIR_DADOS_SITE / "eleicoes.json"
    eleicao = eleicao_do_ano(hoje.year)
    if not eleicao:
        arq.write_text(json.dumps({"gerado_em": agora, "ativo": False, "motivo": f"sem eleição federal em {hoje.year}"},
                                  ensure_ascii=False), encoding="utf-8")
        print(f"✅ eleições: sem eleição federal em {hoje.year} (seção desligada)")
        return []
    turnos = []
    for numero, codigo, data in eleicao["turnos"]:
        try:
            turnos.append(turno(eleicao["ciclo"], numero, codigo, data))
        except requests.HTTPError:  # antes da votação o TSE ainda não publicou o arquivo do turno
            turnos.append({"turno": numero, "data": data, "apurado_pct": 0, "candidatos": [], "por_uf": {}})
    # ninguém no 2º turno (eleito no 1º): a última votação foi o 1º turno
    eleito_no_1o = any(c["situacao"].lower().startswith("eleito") for c in turnos[0]["candidatos"])
    ha_segundo = bool(turnos[1]["candidatos"]) and not eleito_no_1o
    ultima = date.fromisoformat(turnos[1]["data"] if ha_segundo else turnos[0]["data"])
    ate = ultima + timedelta(days=DIAS_DEPOIS)
    arq.write_text(json.dumps({
        "gerado_em": agora, "ativo": hoje <= ate, "ano": hoje.year, "ate": ate.isoformat(), "cargo": "Presidente",
        "turnos": turnos if ha_segundo else turnos[:1], "fonte": "TSE — Divulgação de Resultados (resultados.tse.jus.br)"},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"✅ eleições {hoje.year}: seção " + (f"ativa até {ate.isoformat()}" if hoje <= ate else "encerrada"))
    for t in turnos:
        print(f"✅ eleições {t['turno']}º turno: {t['apurado_pct']}% apurado;",
              ", ".join(f"{c['nome']} {c['pct']}%" for c in t["candidatos"][:3]))
    return turnos


if __name__ == "__main__":
    gerar()
