"""
Planilhas de download com a série histórica completa de cada gráfico de Macro, Juros e Offshore:
site/downloads/macro.xlsx, juros.xlsx e offshore.xlsx (geradas a partir dos JSON do site).

Uso: py -m pipeline.planilhas
"""

import json
from datetime import date

import pandas as pd

from pipeline import DIR_DADOS_SITE, DIR_DOWNLOADS_SITE

ABAS_MACRO = {
    "Inflação": ["ipca", "ipca_12m", "ipca_mm3", "igpm", "igpm_12m", "igpm_mm3", "incc", "incc_12m", "incc_mm3"],
    "Núcleos do IPCA": ["nucleos_media", "nucleos_media_12m", "nucleos_media_mm3",
                        *[f"nucleo_{n}{s}" for n in ("ex0", "ex2", "ex3", "ms", "dp", "p55") for s in ("", "_12m", "_mm3")]],
    "PIB trimestral": ["pib_tri", "pib_12m", "pib_indice", "pib_indice_obs"],
    "PIB anual": ["pib_anual", "pib_nominal"],
    "IBC-Br": ["ibcbr_mensal", "ibcbr_12m", "ibcbr", "ibcbr_dessaz"],
    "Desemprego": ["desemprego"],
    "Selic e juro real": ["selic_meta", "juro_real"],
    "CDI e câmbio (diário)": ["cdi", "usd", "eur"],
    "Política fiscal": ["dbgg", "dlsp", "nfsp_primario", "nfsp_juros", "nfsp_nominal", "nfsp_primario_central",
                        "nfsp_primario_regionais", "nfsp_primario_estatais"],
    "Dívida mobiliária federal": ["dmf_selic", "dmf_pre", "dmf_ipca", "dmf_igpm", "dmf_cambio", "dmf_tr", "dmf_igpdi", "dmf_tjlp",
                                  "dmf_outros", "dmf_prazo"],
}
NOMES_FOCUS = {"ipca": "IPCA (%)", "selic": "Selic fim de ano (% a.a.)", "cambio": "Câmbio fim de ano (R$/US$)", "pib": "PIB (%)"}


def _tabela(series, chaves):
    colunas = {}
    for k in chaves:
        s = series.get(k)
        if s and s["datas"]:
            colunas[f"{s['nome']} ({s['unidade']})"] = pd.Series(s["valores"], index=pd.to_datetime(s["datas"]))
    df = pd.DataFrame(colunas).sort_index()
    df.index.name = "Data"
    return df


def _leia_me(escritor, linhas):
    pd.DataFrame({"Bloomberg de Pobre": linhas}).to_excel(escritor, sheet_name="Leia-me", index=False)


def _ajustar_colunas(escritor):
    for aba in escritor.book.worksheets:
        aba.freeze_panes = "B2"
        for coluna in aba.columns:
            largura = max(len(str(c.value or "")) for c in coluna[:200])
            aba.column_dimensions[coluna[0].column_letter].width = min(max(12, largura + 2), 60)


def gerar_macro():
    macro = json.loads((DIR_DADOS_SITE / "macro.json").read_text(encoding="utf-8"))
    S = macro["series"]
    destino = DIR_DOWNLOADS_SITE / "macro.xlsx"
    with pd.ExcelWriter(destino, engine="openpyxl", datetime_format="DD/MM/YYYY", date_format="DD/MM/YYYY") as w:
        _leia_me(w, [f"Séries macroeconômicas — atualizado em {macro['gerado_em']}",
                     "Fontes: Banco Central (SGS) e boletim Focus. IPCA, PIB e PNAD são do IBGE; IGP-M e INCC são da FGV (via SGS).",
                     "Médias de 3 meses anualizadas: variação acumulada nos últimos 3 meses elevada à 4ª potência, sem ajuste sazonal.",
                     "Média dos núcleos: média simples mensal de EX0, EX3, MS, DP e P55, calculada pelo site.",
                     "Política fiscal: NFSP (necessidade de financiamento do setor público) em 12 meses, % do PIB — positivo = déficit, negativo = superávit (no site o sinal aparece invertido, como resultado).",
                     "Dívida mobiliária federal: participação por indexador (posição em carteira); a do IPCA é calculada por diferença (100% − demais).",
                     "Crédito: estatísticas de crédito do Banco Central (Nota de Crédito), desde 2011; saldos e concessões em R$ milhões, inadimplência = atraso acima de 90 dias.",
                     "Cada aba corresponde a um grupo de gráficos da seção Macro."])
        for aba, chaves in ABAS_MACRO.items():
            _tabela(S, chaves).to_excel(w, sheet_name=aba)
        linhas = [{"Indicador": NOMES_FOCUS.get(k, k), "Ano de referência": ano, "Data": pd.Timestamp(d), "Mediana": v}
                  for k, anos in macro["focus"].items() for ano, serie in anos.items()
                  for d, v in zip(serie["datas"], serie["valores"])]
        pd.DataFrame(linhas).to_excel(w, sheet_name="Focus", index=False)
        # Crédito (pipeline.credito): uma aba por grupo, como na seção Macro → Crédito
        arq_cred = DIR_DADOS_SITE / "credito.json"
        if arq_cred.exists():
            C = json.loads(arq_cred.read_text(encoding="utf-8"))["series"]
            grupos = {"Crédito total": lambda k: not (k.startswith("mod_") or "_pj" in k or "_pf" in k or k.startswith(("endiv", "compr"))),
                      "Crédito PJ": lambda k: "_pj" in k and not k.startswith("mod_"),
                      "Crédito PF": lambda k: ("_pf" in k and not k.startswith("mod_")) or k.startswith(("endiv", "compr")),
                      "Crédito modalidades": lambda k: k.startswith("mod_")}
            for aba, filtro in grupos.items():
                chaves = [k for k in C if filtro(k)]
                if chaves:
                    _tabela(C, chaves).to_excel(w, sheet_name=aba)
        _ajustar_colunas(w)
    return destino


def gerar_juros():
    tes = json.loads((DIR_DADOS_SITE / "tesouro.json").read_text(encoding="utf-8"))
    arq_di = DIR_DADOS_SITE / "curva_di.json"
    di = json.loads(arq_di.read_text(encoding="utf-8")) if arq_di.exists() else None
    destino = DIR_DOWNLOADS_SITE / "juros.xlsx"
    with pd.ExcelWriter(destino, engine="openpyxl", datetime_format="DD/MM/YYYY", date_format="DD/MM/YYYY") as w:
        _leia_me(w, [f"Juros — Tesouro Direto oficial com referência {tes['data_base']}" + (f"; curva DI de {di['curvas']['hoje']['data']}" if di else ""),
                     "Curva DI: arquivo 'Taxas de Mercado para Swaps' da B3 (DI x Pré e DI x IPCA), % a.a., base 252.",
                     "Tesouro oficial: dados abertos do Tesouro Transparente (1 registro por dia útil, 1–2 dias de atraso). Taxas em % a.a.",
                     "Aba 'Tesouro agora (NÃO OFICIAL)': preços do momento lidos do site do Tesouro Direto, sem documentação nem garantia.",
                     "Histórico: taxa e PU de compra de cada título desde o início da série, uma coluna por título."])
        if di:
            linhas = []
            for rotulo, c in di["curvas"].items():
                ipca = {p["dias_uteis"]: p["taxa"] for p in c.get("ipca", [])}
                for p in c["pre"]:
                    linhas.append({"Curva": rotulo, "Data": pd.Timestamp(c["data"]), "Dias úteis": p["dias_uteis"],
                                   "Dias corridos": p["dias_corridos"], "Anos (DU/252)": p["anos"],
                                   "DI x Pré (% a.a.)": p["taxa"], "DI x IPCA (% a.a.)": ipca.get(p["dias_uteis"])})
            pd.DataFrame(linhas).to_excel(w, sheet_name="Curva DI (B3)", index=False)
        nomes = {"prefixado": "Prefixado", "ipca": "IPCA+ (juro real)", "inflacao_implicita": "Inflação implícita"}
        linhas = [{"Curva": rotulo, "Data": pd.Timestamp(c["data"]), "Tipo": nomes.get(tipo, tipo), "Título": p.get("titulo"),
                   "Vencimento": pd.Timestamp(p["vencimento"]), "Anos até o vencimento": p["anos"], "Taxa (% a.a.)": p["taxa"]}
                  for rotulo, c in tes["curvas"].items() for tipo in nomes for p in c.get(tipo, [])]
        pd.DataFrame(linhas).to_excel(w, sheet_name="Curvas do Tesouro", index=False)
        pd.DataFrame([{"Título": t["tipo"], "Vencimento": pd.Timestamp(t["vencimento"]), "Taxa compra (% a.a.)": t["taxa_compra"],
                       "PU compra (R$)": t["pu_compra"]} for t in tes["titulos"]]).to_excel(w, sheet_name="Títulos à venda", index=False)
        tr = tes.get("tempo_real")
        if tr:
            pd.DataFrame([{"Título": t["tipo"], "Vencimento": pd.Timestamp(t["vencimento"]), "Taxa compra agora (% a.a.)": t["taxa_compra"],
                           "PU compra agora (R$)": t["pu_compra"], "Precificado em": t["precificado_em"].replace("T", " ")}
                          for t in tr["titulos"]]).to_excel(w, sheet_name="Tesouro agora (NÃO OFICIAL)", index=False)
        taxas, precos = {}, {}
        for t in tes["titulos"]:
            arq = DIR_DADOS_SITE / "tesouro" / f"{t['id']}.json"
            if not arq.exists():
                continue
            h = json.loads(arq.read_text(encoding="utf-8"))
            nome = f"{h['tipo']} {h['vencimento'][:4]}"
            idx = pd.to_datetime(h["datas"])
            taxas[nome] = pd.Series(h["taxa_compra"], index=idx)
            precos[nome] = pd.Series(h["pu_compra"], index=idx)
        for aba, dados in (("Histórico de taxas", taxas), ("Histórico de PU", precos)):
            df = pd.DataFrame(dados).sort_index().replace(0, pd.NA)
            df.index.name = "Data"
            df.to_excel(w, sheet_name=aba)
        _ajustar_colunas(w)
    return destino


def _serie_pd(s):
    return pd.Series(s["valores"], index=pd.to_datetime(s["datas"])) if s and s.get("datas") else pd.Series(dtype=float)


def gerar_offshore():
    arq = DIR_DADOS_SITE / "offshore.json"
    if not arq.exists():
        return None
    off = json.loads(arq.read_text(encoding="utf-8"))
    T, F, B, E, Z, R = (off.get(k, {}) for k in ("treasuries", "fed", "bls", "bce", "eurostat", "fred"))

    def tabela(colunas):
        df = pd.DataFrame({nome: _serie_pd(s) for nome, s in colunas.items() if s}).sort_index()
        df.index.name = "Data"
        return df

    destino = DIR_DOWNLOADS_SITE / "offshore.xlsx"
    with pd.ExcelWriter(destino, engine="openpyxl", datetime_format="DD/MM/YYYY", date_format="DD/MM/YYYY") as w:
        _leia_me(w, [f"Mundo (exterior) — atualizado em {off['gerado_em']}",
                     "Fontes oficiais: Tesouro dos EUA (Treasuries), Fed de Nova York (EFFR, SOFR, meta dos Fed Funds), BLS (CPI, desemprego, payroll),",
                     "FRED do Fed de St. Louis (PIB, PCE, produção industrial, varejo e confiança do consumidor dos EUA),",
                     "BCE (taxas de depósito e de refinanciamento, €STR, curva AAA da Zona do Euro) e Eurostat (HICP, desemprego, PIB,",
                     "produção industrial e varejo da Zona do Euro). Taxas em % a.a."])
        H = T.get("historico", {})
        tabela({f"Treasury {k} (%)": v for k, v in H.items()}).to_excel(w, sheet_name="Treasuries (diário)")
        linhas = [{"Curva": nome, "Data": pd.Timestamp(c["data"]), "Prazo": p["prazo"], "Anos": p["anos"], "Taxa (% a.a.)": p["taxa"]}
                  for nome, curvas in (("Treasuries nominal", T.get("nominal", {})), ("Treasuries real (TIPS)", T.get("real", {})),
                                       ("Zona do Euro AAA", E.get("curva", {})))
                  for rotulo, c in curvas.items() for p in c["pontos"]]
        pd.DataFrame(linhas).to_excel(w, sheet_name="Curvas", index=False)
        tabela({"EFFR (%)": F.get("effr"), "SOFR (%)": F.get("sofr"), "Meta Fed Funds — mínimo (%)": F.get("meta_min"),
                "Meta Fed Funds — máximo (%)": F.get("meta_max")}).to_excel(w, sheet_name="Fed Funds e SOFR")
        tabela({"Taxa de depósito do BCE (%)": E.get("deposito"), "Refinanciamento (MRO) (%)": E.get("refinanciamento"), "€STR (%)": E.get("estr"),
                "Zona do Euro AAA 10 anos (%)": E.get("aaa_10a")}
               ).to_excel(w, sheet_name="BCE")
        tabela({"CPI 12 meses (%)": B.get("cpi_12m"), "CPI núcleo 12 meses (%)": B.get("cpi_nucleo_12m"), "CPI mensal dessaz. (%)": B.get("cpi_mensal"),
                "CPI núcleo mensal dessaz. (%)": B.get("cpi_nucleo_mensal"), "Desemprego (%)": B.get("desemprego"),
                "Payroll (mil vagas no mês)": B.get("payroll_var")}).to_excel(w, sheet_name="EUA (BLS)")
        if R:
            tabela({"PIB real tri/tri anualizado (%)": R.get("pib_tri_anual"), "PIB real contra 1 ano antes (%)": R.get("pib_12m"),
                    "PCE 12 meses (%)": R.get("pce_12m"), "PCE núcleo 12 meses (%)": R.get("pce_nucleo_12m"), "PCE mensal (%)": R.get("pce_mensal"),
                    "PCE núcleo mensal (%)": R.get("pce_nucleo_mensal"), "Produção industrial 12 meses (%)": R.get("producao_12m"),
                    "Produção industrial mensal (%)": R.get("producao_mensal"), "Varejo 12 meses (%)": R.get("varejo_12m"),
                    "Varejo mensal (%)": R.get("varejo_mensal"), "Confiança do consumidor — Michigan (índice)": R.get("confianca")}
                   ).to_excel(w, sheet_name="EUA (FRED)")
        tabela({"HICP 12 meses (%)": Z.get("hicp_12m"), "HICP núcleo 12 meses (%)": Z.get("hicp_nucleo_12m"),
                "HICP serviços 12 meses (%)": Z.get("hicp_servicos_12m"), "Desemprego (%)": Z.get("desemprego"),
                "PIB tri/tri dessaz. (%)": Z.get("pib_tri"), "PIB contra mesmo tri do ano anterior (%)": Z.get("pib_12m"),
                "Produção industrial 12 meses (%)": Z.get("producao_12m"), "Produção industrial mensal (%)": Z.get("producao_mensal"),
                "Varejo (volume) 12 meses (%)": Z.get("varejo_12m"), "Varejo (volume) mensal (%)": Z.get("varejo_mensal")}
               ).to_excel(w, sheet_name="Zona do Euro (Eurostat)")
        _ajustar_colunas(w)
    return destino


def gerar():
    DIR_DOWNLOADS_SITE.mkdir(parents=True, exist_ok=True)
    feitos = [f for f in (gerar_macro(), gerar_juros(), gerar_offshore()) if f]
    for f in feitos:
        print(f"✅ {f.name}: {f.stat().st_size // 1024} KB")
    return feitos


if __name__ == "__main__":
    gerar()
