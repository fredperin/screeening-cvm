"""
Gera, para cada empresa da lista selecionada, o JSON de séries do site
(site/dados/empresas/{id}.json), o Excel padrão pronto para download
(site/downloads/{id}.xlsx, histórico completo) e o índice site/dados/empresas.json.

Uso: py -m pipeline.gerar_empresas [TICKER ...]   (sem argumentos = todas)
"""

import contextlib
import io
import json
import sys
import time
from datetime import date

import pandas as pd

from pipeline import DIR_DADOS_SITE, DIR_DOWNLOADS_SITE, DIR_INTERMEDIARIO
from pipeline.cvm_lote import atualizar_base_cvm, carregar_empresa
from pipeline.series_empresa import adicionar_indicadores, aplicar_anual_dfp, montar_trimestral, montar_visoes, para_json
from src import cvm_itr
from src.cvm_itr import buscar_dados_cadastrais, buscar_dados_fca, buscar_itr, montar_documento_padrao
from src.exportar import exportar_documento_padrao
from src.screening import universo_selecionado

ANO_INICIAL = 2011
ESCALAS = {"MIL": 1000, "UNIDADE": 1}
DIR_EMPRESAS = DIR_DADOS_SITE / "empresas"
ARQ_LOG = DIR_INTERMEDIARIO / "gerar_empresas.log"


def id_empresa(tickers):
    return tickers[0]


def montar_blocos(base, tipo="con"):
    """Blocos do documento padrão (histórico completo) a partir da base em memória."""
    cvm_itr.usar_base_pre_carregada(base)
    try:
        anos = list(range(ANO_INICIAL, date.today().year + 1))
        return montar_documento_padrao(buscar_itr(base["CNPJ_CIA"].iloc[0], anos, tipo=tipo), ano_inicio=ANO_INICIAL)
    finally:
        cvm_itr.usar_base_pre_carregada(None)


def fator_escala(base):
    """Fator para reais. Se a empresa mudou de escala ao longo dos anos, devolve None."""
    escalas = base["ESCALA_MOEDA"].dropna().unique()
    if len(escalas) == 1:
        return ESCALAS.get(escalas[0], 1)
    return None


def mes_fim_exercicio(base):
    """Mês em que termina o exercício social, pelo fim dos períodos anuais (DFP) da DRE."""
    anual = base[(base["FONTE"] == "DFP") & (base["SIGLA"] == "DRE")]["DT_FIM_EXERC"].dropna()
    return int(pd.to_datetime(anual).dt.month.mode().iloc[0]) if not anual.empty else 12


def processar(empresa, log):
    base = carregar_empresa(empresa.CNPJ_CIA)
    if base.empty:
        log.write(f"[{empresa.DENOM_SOCIAL}] sem dados na base da CVM\n")
        return None, None

    with contextlib.redirect_stdout(log):
        blocos = montar_blocos(base)
        fator = fator_escala(base)
        if fator is None:
            # Escala mista entre anos: refaz os blocos com tudo já convertido para reais
            convertida = base.copy()
            convertida["VL_CONTA"] = convertida["VL_CONTA"] * convertida["ESCALA_MOEDA"].map(ESCALAS).fillna(1)
            blocos_reais, fator = montar_blocos(convertida), 1
        else:
            blocos_reais = blocos

    q, notas = montar_trimestral(blocos_reais, fator, base)
    visoes = adicionar_indicadores(aplicar_anual_dfp(montar_visoes(q, mes_fim_exercicio(base)), base))
    dados = {
        "id": id_empresa(empresa.tickers_lista),
        "nome": empresa.DENOM_SOCIAL,
        "cnpj": empresa.CNPJ_CIA,
        "tickers": empresa.tickers_lista,
        "setor": empresa.SETOR_ATIV if isinstance(empresa.SETOR_ATIV, str) else None,
        "unidade": "R$",
        "mes_fim_exercicio": mes_fim_exercicio(base),
        "gerado_em": date.today().isoformat(),
        "notas": notas,
        **para_json(visoes),
    }
    return dados, blocos


def tabelas_dividendos(id_, dados):
    """Tabelas da aba Dividendos: proventos da B3, pagos na DFC por exercício e por ação por ano."""
    arq = DIR_DADOS_SITE / "proventos" / f"{id_}.json"
    prov = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}

    b3 = pd.DataFrame([{
        "Tipo": p["tipo"], "Classe": p["classe"], "Data-com": p["data_com"], "Pagamento": p["pagamento"],
        "R$ por ação": p["valor"], "Referente a": p["referente"],
    } for p in prov.get("proventos_b3", [])])

    anual = dados["anual"]
    vazio = [None] * len(anual["periodos"])
    s = {k: anual["series"].get(k, vazio) for k in ("div_pagos", "lucro_liquido", "payout")}
    dfc = pd.DataFrame({
        "Exercício (fim)": anual["periodos"],
        "Dividendos + JCP pagos (R$)": s["div_pagos"],
        "Lucro líquido (R$)": s["lucro_liquido"],
        "Payout (%)": [round(x * 100, 1) if x is not None else None for x in s["payout"]],
    }).iloc[::-1]

    por_ano = prov.get("proventos_por_acao_ano") or {}
    yahoo = pd.DataFrame({"Ano": list(por_ano), "R$ por ação": list(por_ano.values())}).iloc[::-1]
    papel = prov.get("papel_referencia") or "-"
    return [
        ("Proventos anunciados — B3 (a API da B3 traz cerca dos últimos 12 meses)", b3),
        ("Dividendos e JCP pagos por exercício — DFC (linhas identificadas por descrição) e payout", dfc),
        (f"Proventos por ação por ano — {papel} (Yahoo Finance, não oficial)", yahoo),
    ]


def gerar_excel(empresa, dados, blocos, log):
    id_ = dados["id"]
    with contextlib.redirect_stdout(log):
        cadastro = {**buscar_dados_cadastrais(empresa.CNPJ_CIA), **buscar_dados_fca(empresa.CNPJ_CIA)}
        exportar_documento_padrao(
            blocos, empresa.DENOM_SOCIAL, ANO_INICIAL, date.today().year,
            dados_cadastrais=cadastro, destino=DIR_DOWNLOADS_SITE / f"{id_}.xlsx",
            abas_extras=[("Dividendos", tabelas_dividendos(id_, dados))],
        )


def _ultimo(visao, serie):
    valores = visao["series"].get(serie) or []
    return valores[-1] if valores else None


def gerar_indice():
    """Índice do site (site/dados/empresas.json) a partir dos JSONs de cada empresa já gerados."""
    indice = []
    for arq in sorted(DIR_EMPRESAS.glob("*.json")):
        d = json.loads(arq.read_text(encoding="utf-8"))
        tri, ltm = d["trimestral"], d["ltm"]
        indice.append({
            "id": d["id"], "nome": d["nome"], "cnpj": d["cnpj"], "tickers": d["tickers"], "setor": d["setor"],
            "ultimo_periodo": tri["periodos"][-1] if tri["periodos"] else None,
            "receita_tri": _ultimo(tri, "receita"), "cresc_receita_tri": _ultimo(tri, "cresc_receita"),
            "lucro_tri": _ultimo(tri, "lucro_liquido"), "cresc_lucro_tri": _ultimo(tri, "cresc_lucro"),
            "receita_ltm": _ultimo(ltm, "receita"), "lucro_ltm": _ultimo(ltm, "lucro_liquido"),
            "ebitda_ltm": _ultimo(ltm, "ebitda"), "ebit_ltm": _ultimo(ltm, "ebit"), "fcf_ltm": _ultimo(ltm, "fcf"),
            "pl": _ultimo(ltm, "pl"), "divida_liquida": _ultimo(ltm, "divida_liquida"),
            "m_liquida_ltm": _ultimo(ltm, "m_liquida"), "roe": _ultimo(ltm, "roe"), "roic": _ultimo(ltm, "roic"),
            "dl_ebitda": _ultimo(ltm, "dl_ebitda"),
        })
    indice.sort(key=lambda e: e["nome"])
    (DIR_DADOS_SITE / "empresas.json").write_text(json.dumps(indice, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return indice


def main(filtro=None, excel=True):
    universo = universo_selecionado()
    cnpjs = set(universo["CNPJ_CIA"].str.replace(r"\D", "", regex=True))
    atualizar_base_cvm(cnpjs)

    if filtro:
        universo = universo[universo["tickers_lista"].apply(lambda ts: any(t in filtro for t in ts))]

    DIR_EMPRESAS.mkdir(parents=True, exist_ok=True)
    indice, falhas = [], []
    inicio = time.time()
    with open(ARQ_LOG, "w", encoding="utf-8") as log:
        for i, empresa in enumerate(universo.itertuples(), start=1):
            try:
                dados, blocos = processar(empresa, log)
                if dados is not None and excel:
                    gerar_excel(empresa, dados, blocos, log)
            except Exception as e:
                falhas.append(f"{empresa.DENOM_SOCIAL}: {e!r}")
                log.write(f"[{empresa.DENOM_SOCIAL}] ERRO {e!r}\n")
                continue
            if dados is None:
                falhas.append(f"{empresa.DENOM_SOCIAL}: sem dados")
                continue
            (DIR_EMPRESAS / f"{dados['id']}.json").write_text(
                json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            tri = dados["trimestral"]["periodos"]
            indice.append({
                "id": dados["id"], "nome": dados["nome"], "cnpj": dados["cnpj"], "tickers": dados["tickers"],
                "setor": dados["setor"], "ultimo_periodo": tri[-1] if tri else None,
            })
            if i % 25 == 0:
                print(f"   {i}/{len(universo)} empresas ({time.time() - inicio:.0f}s)")

    if not filtro:
        gerar_indice()
    print(f"✅ {len(indice)} empresas geradas em {time.time() - inicio:.0f}s; {len(falhas)} falhas")
    for f in falhas:
        print("   ⚠️", f)
    return indice, falhas


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(set(args) or None, excel="--sem-excel" not in sys.argv)
