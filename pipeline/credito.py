"""
Estatísticas de crédito do Banco Central (Nota de Crédito, SGS) para a aba Macro → Crédito:
saldo, crédito/PIB, concessões, juros, spread, custo do crédito (ICC), inadimplência, atraso de
15 a 90 dias, prazo médio, modalidades e endividamento/comprometimento de renda das famílias.
Total, pessoas jurídicas e pessoas físicas; recursos livres e direcionados. Mensal, desde 2011
(metodologia atual), publicado cerca de 30 dias depois do fim do mês.

Códigos conferidos no catálogo de dados abertos do BC (dadosabertos.bcb.gov.br).
Uma série que falhar fica com a versão anterior; as outras seguem atualizadas.

Saída: site/dados/credito.json. Uso: py -m pipeline.credito
"""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd

from pipeline import DIR_DADOS_SITE
from pipeline.macro import _empacotar, _regrediu, baixar_sgs

INICIO = 2011
ARQ = DIR_DADOS_SITE / "credito.json"

# chave: (código SGS, nome, unidade). Saldos e concessões em R$ milhões no SGS.
SERIES = {
    # ---- Total
    "saldo_total": (20539, "Saldo da carteira de crédito — total", "R$ milhões"),
    "saldo_livres": (20542, "Saldo — recursos livres", "R$ milhões"),
    "saldo_dir": (20593, "Saldo — recursos direcionados", "R$ milhões"),
    "pib_total": (20622, "Saldo da carteira de crédito em % do PIB", "% PIB"),
    "pib_livres": (20625, "Crédito com recursos livres em % do PIB", "% PIB"),
    "pib_dir": (20628, "Crédito com recursos direcionados em % do PIB", "% PIB"),
    "conc_total": (20631, "Concessões de crédito — total", "R$ milhões"),
    "conc_total_sa": (24439, "Concessões — total, dessazonalizadas", "R$ milhões"),
    "conc_livres_sa": (24442, "Concessões — livres, dessazonalizadas", "R$ milhões"),
    "conc_dir_sa": (24445, "Concessões — direcionados, dessazonalizadas", "R$ milhões"),
    "taxa_total": (20714, "Taxa média de juros — total", "% a.a."),
    "taxa_livres": (20717, "Taxa média de juros — livres", "% a.a."),
    "taxa_dir": (20756, "Taxa média de juros — direcionados", "% a.a."),
    "spread_total": (20783, "Spread médio — total", "p.p."),
    "icc_total": (25351, "Indicador de Custo do Crédito (ICC) — total", "% a.a."),
    "inad_total": (21082, "Inadimplência (atraso > 90 dias) — total", "%"),
    "inad_livres": (21085, "Inadimplência — livres", "%"),
    "inad_dir": (21132, "Inadimplência — direcionados", "%"),
    "atraso_total": (21003, "Atraso entre 15 e 90 dias — total", "%"),
    "prazo_total": (20924, "Prazo médio da carteira — total", "meses"),
    # ---- Pessoas jurídicas
    "saldo_pj": (20540, "Saldo — pessoas jurídicas", "R$ milhões"),
    "saldo_pj_livres": (20543, "Saldo PJ — livres", "R$ milhões"),
    "saldo_pj_dir": (20594, "Saldo PJ — direcionados", "R$ milhões"),
    "pib_pj": (20623, "Crédito a PJ em % do PIB", "% PIB"),
    "pib_pj_livres": (20626, "Crédito a PJ com recursos livres em % do PIB", "% PIB"),
    "pib_pj_dir": (20629, "Crédito a PJ com recursos direcionados em % do PIB", "% PIB"),
    "conc_pj": (20632, "Concessões PJ — total", "R$ milhões"),
    "conc_pj_sa": (24440, "Concessões PJ — dessazonalizadas", "R$ milhões"),
    "conc_pj_livres_sa": (24443, "Concessões PJ — livres, dessazonalizadas", "R$ milhões"),
    "conc_pj_dir_sa": (24446, "Concessões PJ — direcionados, dessazonalizadas", "R$ milhões"),
    "taxa_pj": (20715, "Taxa média de juros PJ — total", "% a.a."),
    "taxa_pj_livres": (20718, "Taxa média de juros PJ — livres", "% a.a."),
    "taxa_pj_dir": (20757, "Taxa média de juros PJ — direcionados", "% a.a."),
    "spread_pj": (20784, "Spread médio PJ", "p.p."),
    "icc_pj": (25352, "ICC — pessoas jurídicas", "% a.a."),
    "inad_pj": (21083, "Inadimplência PJ — total", "%"),
    "inad_pj_livres": (21086, "Inadimplência PJ — livres", "%"),
    "inad_pj_dir": (21133, "Inadimplência PJ — direcionados", "%"),
    "atraso_pj": (21004, "Atraso entre 15 e 90 dias — PJ", "%"),
    "prazo_pj": (20925, "Prazo médio da carteira PJ — total", "meses"),
    "prazo_pj_livres": (20928, "Prazo médio da carteira PJ — livres", "meses"),
    "prazo_pj_dir": (20975, "Prazo médio da carteira PJ — direcionados", "meses"),
    # ---- Pessoas físicas
    "saldo_pf": (20541, "Saldo — pessoas físicas", "R$ milhões"),
    "saldo_pf_livres": (20570, "Saldo PF — livres", "R$ milhões"),
    "saldo_pf_dir": (20606, "Saldo PF — direcionados", "R$ milhões"),
    "pib_pf": (20624, "Crédito a PF em % do PIB", "% PIB"),
    "pib_pf_livres": (20627, "Crédito a PF com recursos livres em % do PIB", "% PIB"),
    "pib_pf_dir": (20630, "Crédito a PF com recursos direcionados em % do PIB", "% PIB"),
    "conc_pf": (20633, "Concessões PF — total", "R$ milhões"),
    "conc_pf_sa": (24441, "Concessões PF — dessazonalizadas", "R$ milhões"),
    "conc_pf_livres_sa": (24444, "Concessões PF — livres, dessazonalizadas", "R$ milhões"),
    "conc_pf_dir_sa": (24447, "Concessões PF — direcionados, dessazonalizadas", "R$ milhões"),
    "taxa_pf": (20716, "Taxa média de juros PF — total", "% a.a."),
    "taxa_pf_livres": (20740, "Taxa média de juros PF — livres", "% a.a."),
    "taxa_pf_dir": (20768, "Taxa média de juros PF — direcionados", "% a.a."),
    "spread_pf": (20785, "Spread médio PF", "p.p."),
    "icc_pf": (25353, "ICC — pessoas físicas", "% a.a."),
    "inad_pf": (21084, "Inadimplência PF — total", "%"),
    "inad_pf_livres": (21112, "Inadimplência PF — livres", "%"),
    "inad_pf_dir": (21145, "Inadimplência PF — direcionados", "%"),
    "atraso_pf": (21005, "Atraso entre 15 e 90 dias — PF", "%"),
    "prazo_pf": (20926, "Prazo médio da carteira PF — total", "meses"),
    "prazo_pf_livres": (20954, "Prazo médio da carteira PF — livres", "meses"),
    "prazo_pf_dir": (20987, "Prazo médio da carteira PF — direcionados", "meses"),
    "endiv": (29037, "Endividamento das famílias com o SFN (% da renda de 12 meses)", "%"),
    "endiv_sem_hab": (29038, "Endividamento das famílias sem crédito habitacional (% da renda)", "%"),
    "compr": (29034, "Comprometimento de renda com o serviço da dívida (dessaz.)", "%"),
    "compr_juros": (29033, "Comprometimento de renda com juros (dessaz.)", "%"),
    "compr_amort": (29036, "Comprometimento de renda com amortização (dessaz.)", "%"),
}

# Modalidades: (chave, nome, códigos de saldo, taxa média de juros e inadimplência)
MODALIDADES = {
    "pj": [
        ("giro", "Capital de giro", 20550, 20725, 21093),
        ("duplicatas", "Desconto de duplicatas e recebíveis", 20544, 20719, 21087),
        ("conta_garantida", "Conta garantida", 20551, 20726, 21094),
        ("veiculos", "Aquisição de veículos", 20553, 20728, 21096),
        ("cartao", "Cartão de crédito total", 20564, 22021, 21106),
        ("bndes_invest", "Investimentos com recursos do BNDES", 20602, 20765, 21141),
        ("bndes_giro", "Capital de giro com recursos do BNDES", 20601, 20764, 21140),
        ("rural", "Crédito rural", 20597, 20760, 21136),
        ("imobiliario", "Financiamento imobiliário", 20600, 20763, 21139),
    ],
    "pf": [
        ("cartao_rotativo", "Cartão de crédito rotativo", 20587, 22022, 21127),
        ("cartao", "Cartão de crédito total", 20590, 22024, 21129),
        ("cheque", "Cheque especial", 20573, 20741, 21113),
        ("pessoal", "Crédito pessoal não consignado", 20574, 20742, 21114),
        ("consignado", "Crédito consignado", 20579, 20747, 21119),
        ("veiculos", "Aquisição de veículos", 20581, 20749, 21121),
        ("imobiliario", "Financiamento imobiliário", 20612, 20774, 21151),
        ("rural", "Crédito rural", 20609, 20771, 21148),
    ],
}
for grupo, lista in MODALIDADES.items():
    for chave, nome, c_saldo, c_taxa, c_inad in lista:
        SERIES[f"mod_{grupo}_{chave}_saldo"] = (c_saldo, f"{nome} ({grupo.upper()}) — saldo", "R$ milhões")
        SERIES[f"mod_{grupo}_{chave}_taxa"] = (c_taxa, f"{nome} ({grupo.upper()}) — taxa média de juros", "% a.a.")
        SERIES[f"mod_{grupo}_{chave}_inad"] = (c_inad, f"{nome} ({grupo.upper()}) — inadimplência", "%")


def _crescimento_12m(s):
    return ((s / s.shift(12) - 1) * 100).dropna()


def _baixar(codigo):
    try:
        return baixar_sgs(codigo, inicio=INICIO, janela=20)  # mensal: uma consulta só desde 2011
    except Exception as e:  # noqa: BLE001 — a falha vai para a lista e a série fica com a versão anterior
        return e


def gerar():
    anteriores = json.loads(ARQ.read_text(encoding="utf-8"))["series"] if ARQ.exists() else {}
    saida, falhas = {}, []
    # poucas consultas em paralelo (a API do BC aguenta bem; mais que isso arrisca bloqueio)
    with ThreadPoolExecutor(max_workers=6) as ex:
        baixadas = dict(zip(SERIES, ex.map(_baixar, [c for c, _, _ in SERIES.values()])))
    for chave, (codigo, nome, un) in SERIES.items():
        try:
            nova = baixadas[chave]
            if isinstance(nova, Exception):
                raise nova
            problema = _regrediu(nova, anteriores.get(chave))
            if problema:
                raise RuntimeError(problema)
            saida[chave] = _empacotar(nova, nome, un, casas=2)
        except Exception as e:
            falhas.append(f"{chave} (SGS {codigo}): {e}"[:200])
            if chave in anteriores:
                saida[chave] = anteriores[chave]
    if len(falhas) == len(SERIES):
        raise RuntimeError("nenhuma série de crédito respondeu")

    # crescimento do saldo em 12 meses (calculado aqui)
    for k in ("saldo_total", "saldo_pj", "saldo_pf"):
        if k in saida:
            s = pd.Series(saida[k]["valores"], index=pd.to_datetime(saida[k]["datas"]), dtype=float)
            saida[f"{k}_12m"] = _empacotar(_crescimento_12m(s), f"{saida[k]['nome']} — crescimento em 12 meses", "%", casas=2)

    ARQ.write_text(json.dumps({"gerado_em": date.today().isoformat(), "series": saida, "modalidades": {
        g: [{"k": k, "nome": n} for k, n, *_ in lista] for g, lista in MODALIDADES.items()}, "falhas": falhas},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ultimo = saida.get("saldo_total", {}).get("datas", ["—"])[-1]
    print(f"✅ crédito: {len(saida)} séries (último mês {ultimo}); {len(falhas)} falhas")
    for f in falhas:
        print("   ⚠️", f)
    return ARQ


if __name__ == "__main__":
    gerar()
