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
from pipeline.cvm_lote import atualizar_base_cvm, carregar_empresa, consolidado_ou_individual, corrigir_escala_trocada
from pipeline.series_empresa import adicionar_indicadores, aplicar_anual_dfp, demonstracoes, montar_trimestral, montar_visoes, para_json
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
    """Blocos do documento padrão (histórico completo) a partir da base em memória, e a DRE completa
    (todas as contas, trimestre isolado) para a aba Resultados do site."""
    cvm_itr.usar_base_pre_carregada(base)
    try:
        anos = list(range(ANO_INICIAL, date.today().year + 1))
        dem = buscar_itr(base["CNPJ_CIA"].iloc[0], anos, tipo=tipo)
        return montar_documento_padrao(dem, ano_inicio=ANO_INICIAL), dre_trimestral_completa(dem)
    finally:
        cvm_itr.usar_base_pre_carregada(None)


def dre_trimestral_completa(dem):
    """DRE com todas as contas (sem limite de nível), trimestre isolado; índice = código, colunas = data de fim.
    attrs["descricao"] guarda a descrição de cada código."""
    from src.padrao_visual import filtrar_data_minima, isolar_trimestres
    dre = dem.get("Demonstração do Resultado", pd.DataFrame())
    if dre.empty:
        return pd.DataFrame()
    iso = filtrar_data_minima(isolar_trimestres(dre), f"{ANO_INICIAL}-01-01")
    codigos = list(iso.index.get_level_values("CD_CONTA"))
    descricao = dict(zip(codigos, iso.index.get_level_values("DS_CONTA")))
    iso.index = codigos
    iso.columns = [date.fromisoformat(c.split(" a ")[1]) for c in iso.columns]
    iso = iso[~iso.index.duplicated(keep="last")]
    iso.attrs["descricao"] = descricao
    return iso


def fator_escala(base):
    """Fator para reais da escala do envio mais recente (os blocos já vêm convertidos para ela)."""
    validas = base.dropna(subset=["ESCALA_MOEDA"])
    if validas.empty:
        return 1
    return ESCALAS.get(validas.loc[validas["DT_REFER"].idxmax(), "ESCALA_MOEDA"], 1)


def mes_fim_exercicio(base):
    """Mês em que termina o exercício social, pelo fim dos períodos anuais (DFP) da DRE."""
    anual = base[(base["FONTE"] == "DFP") & (base["SIGLA"] == "DRE")]["DT_FIM_EXERC"].dropna()
    return int(pd.to_datetime(anual).dt.month.mode().iloc[0]) if not anual.empty else 12


def _periodos_individuais(base):
    """Datas em que a DRE vem do individual (a empresa não consolidava): fica registrado no JSON."""
    ind = base[(base["TIPO_ORIGEM"] == "ind") & (base["SIGLA"] == "DRE")]
    return sorted(ind["DT_FIM_EXERC"].astype(str).unique().tolist())


def processar(empresa, log):
    cvm_itr.AJUSTES.clear()  # ajustes aplicados aos dados desta empresa (aba "Histórico de ajustes")
    # consolidado sempre que existir com números; individual só onde a empresa não consolida
    base = consolidado_ou_individual(corrigir_escala_trocada(carregar_empresa(empresa.CNPJ_CIA)))
    if base.empty:
        log.write(f"[{empresa.DENOM_SOCIAL}] sem dados na base da CVM\n")
        return None, None

    with contextlib.redirect_stdout(log):
        blocos, dre_completa = montar_blocos(base)
    fator = fator_escala(base)

    q, notas = montar_trimestral(blocos, fator, base)
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
        "notas": {**notas, "individual": _periodos_individuais(base)},
        **para_json(visoes),
        # DRE e Balanço com as contas do Excel (aba Resultados do site)
        "demonstracoes": demonstracoes(blocos, fator, base, visoes, dre_completa=dre_completa),
        "ajustes": sorted(cvm_itr.AJUSTES, key=lambda a: a["periodo"], reverse=True),
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
            "dl_ebitda": _ultimo(ltm, "dl_ebitda"), "dl_ebitda_ifrs16": _ultimo(ltm, "dl_ebitda_ifrs16"),
            "divida_liquida_ifrs16": _ultimo(ltm, "divida_liquida_ifrs16"), "arrendamentos": _ultimo(ltm, "arrendamentos"),
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
