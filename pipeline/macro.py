"""
Séries macroeconômicas do Banco Central (API SGS) e expectativas do boletim
Focus (API Olinda) para a seção Macro do site -> site/dados/macro.json
"""

import json
import time
from datetime import date, timedelta
from urllib.parse import quote

import pandas as pd
import requests

from pipeline import DIR_DADOS_SITE

URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial={ini}&dataFinal={fim}"
URL_FOCUS = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais"
INICIO = 2000

SERIES = {
    "ipca": (433, "IPCA (mensal)", "% a.m."),
    "igpm": (189, "IGP-M (mensal)", "% a.m."),
    "incc": (192, "INCC-DI (mensal)", "% a.m."),
    # Núcleos do IPCA calculados pelo Banco Central
    "nucleo_ex0": (11427, "Núcleo EX0 (exclusão: alimentação no domicílio e monitorados)", "% a.m."),
    "nucleo_ex2": (27838, "Núcleo EX2 (exclusão)", "% a.m."),
    "nucleo_ex3": (27839, "Núcleo EX3 (exclusão)", "% a.m."),
    "nucleo_ms": (4466, "Núcleo MS (médias aparadas com suavização)", "% a.m."),
    "nucleo_dp": (16122, "Núcleo DP (dupla ponderação)", "% a.m."),
    "nucleo_p55": (28750, "Núcleo P55 (percentil 55)", "% a.m."),
    "selic_meta": (432, "Selic meta", "% a.a."),
    "cdi": (4389, "CDI anualizado", "% a.a."),
    "usd": (1, "Dólar PTAX (venda)", "R$"),
    "eur": (21619, "Euro PTAX (venda)", "R$"),
    "pib_anual": (7326, "PIB, variação real anual", "%"),
    "pib_nominal": (1207, "PIB anual em R$ correntes", "R$"),
    "pib_indice": (22109, "PIB trimestral, índice dessazonalizado", "índice"),
    "pib_indice_obs": (22099, "PIB trimestral, índice observado (sem ajuste)", "índice"),
    "ibcbr": (24363, "IBC-Br, índice observado (sem ajuste)", "índice"),
    "ibcbr_dessaz": (24364, "IBC-Br, índice dessazonalizado", "índice"),
}
# Contas públicas (Banco Central, Estatísticas Fiscais; nomes conferidos no catálogo de dados abertos do BC).
# NFSP = necessidade de financiamento do setor público: positivo = déficit. No site o sinal é invertido para
# "resultado" (superávit positivo). Falha numa série fiscal não derruba o resto do Macro.
SERIES_FISCAIS = {
    "nfsp_primario": (5793, "NFSP 12 meses, resultado primário — setor público consolidado", "% PIB"),
    "nfsp_primario_central": (5783, "NFSP 12 meses, resultado primário — Governo Federal e Banco Central", "% PIB"),
    "nfsp_primario_regionais": (5786, "NFSP 12 meses, resultado primário — governos estaduais e municipais", "% PIB"),
    "nfsp_primario_estatais": (5789, "NFSP 12 meses, resultado primário — empresas estatais", "% PIB"),
    "nfsp_juros": (5760, "NFSP 12 meses, juros nominais — setor público consolidado", "% PIB"),
    "nfsp_nominal": (5727, "NFSP 12 meses, resultado nominal — setor público consolidado", "% PIB"),
    "dlsp": (4513, "Dívida líquida do setor público — setor público consolidado", "% PIB"),
    "dbgg": (13762, "Dívida bruta do governo geral (metodologia a partir de 2008)", "% PIB"),
    "dmf_selic": (4177, "Dívida mobiliária federal — participação Over/Selic", "%"),
    "dmf_pre": (4178, "Dívida mobiliária federal — participação prefixada", "%"),
    "dmf_cambio": (4173, "Dívida mobiliária federal — participação câmbio", "%"),
    "dmf_tr": (4174, "Dívida mobiliária federal — participação TR", "%"),
    "dmf_igpm": (4175, "Dívida mobiliária federal — participação IGP-M", "%"),
    "dmf_igpdi": (4176, "Dívida mobiliária federal — participação IGP-DI", "%"),
    "dmf_tjlp": (4179, "Dívida mobiliária federal — participação TJLP", "%"),
    "dmf_outros": (4180, "Dívida mobiliária federal — participação outros", "%"),
    "dmf_prazo": (10618, "Dívida mobiliária federal — prazo médio dos títulos emitidos", "meses"),
}
SERIES_NUCLEOS = [k for k in SERIES if k.startswith("nucleo_")]
FOCUS = {"ipca": "IPCA", "selic": "Selic", "cambio": "Câmbio", "pib": "PIB Total"}


def _get(url, params=None, tentativas=4):
    for i in range(tentativas):
        try:
            r = requests.get(url, params=params, timeout=60)
            if r.status_code == 404:
                return []
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError):
            if i == tentativas - 1:
                raise
            time.sleep(2 * (i + 1))


def baixar_sgs(codigo, inicio=INICIO, janela=10):
    """Série completa desde `inicio` (2000), em janelas de `janela` anos (10 = limite da API para séries diárias;
    séries mensais aceitam janelas maiores, o que reduz o número de consultas)."""
    partes, hoje = [], date.today()
    for ano in range(inicio, hoje.year + 1, janela):
        ini, fim = date(ano, 1, 1), min(date(ano + janela - 1, 12, 31), hoje)
        # A API às vezes devolve {"erro":{}} ou HTML para uma janela válida e guarda essa resposta em cache
        # para a mesma URL: cada nova tentativa usa outra data final (datas futuras são aceitas)
        finais = [date(ano + janela - 1, 12, 31), fim, fim - timedelta(days=1), date(ano + janela - 1, 12, 30), fim - timedelta(days=2)]
        for tentativa, final in enumerate(finais):
            try:
                dados = _get(URL_SGS.format(codigo=codigo, ini=ini.strftime("%d/%m/%Y"), fim=final.strftime("%d/%m/%Y")),
                             tentativas=2)
            except (requests.RequestException, ValueError):
                dados = None
            if isinstance(dados, list):
                break
            time.sleep(2 * (tentativa + 1))
        else:
            raise RuntimeError(f"SGS {codigo}: sem resposta válida para {ini:%Y}–{fim:%Y}")
        partes.extend(dados)
    if not partes:
        return pd.Series(dtype=float)
    df = pd.DataFrame(partes)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    serie = pd.to_numeric(df["valor"], errors="coerce").set_axis(df["data"])
    serie = serie[~serie.index.duplicated(keep="last")].sort_index()
    return serie[serie.index <= pd.Timestamp(hoje)].dropna()


def acumulado_12m(mensal):
    return ((1 + mensal / 100).rolling(12).apply(lambda x: x.prod(), raw=True) - 1) * 100


def mm3_anualizada(mensal):
    """Variação acumulada nos últimos 3 meses levada ao equivalente anual (sem ajuste sazonal)."""
    return (((1 + mensal / 100).rolling(3).apply(lambda x: x.prod(), raw=True)) ** 4 - 1) * 100


NUCLEOS_MEDIA = ["nucleo_ex0", "nucleo_ex3", "nucleo_ms", "nucleo_dp", "nucleo_p55"]


def _empacotar(serie, nome, unidade, casas=4):
    return {
        "nome": nome, "unidade": unidade,
        "datas": [d.strftime("%Y-%m-%d") for d in serie.index],
        "valores": [round(float(v), casas) for v in serie.values],
    }


def baixar_focus(indicador, todos_os_anos=False):
    """Mediana diária das expectativas (ano corrente e seguinte, ou todos os anos projetados), desde 2 anos atrás."""
    hoje = date.today()
    filtro = (f"Indicador eq '{indicador}' and baseCalculo eq 0 and Data ge '{hoje.year - 2}-01-01'")
    # O Olinda rejeita espaço codificado como "+" (padrão do requests): monta a URL com %20
    url = (f"{URL_FOCUS}?$filter={quote(filtro)}&$select=Data,DataReferencia,Mediana"
           f"&$format=json&$top=100000")
    dados = _get(url)
    df = pd.DataFrame(dados.get("value", []) if isinstance(dados, dict) else [])
    saida = {}
    anos = sorted({int(a) for a in df["DataReferencia"].unique() if str(a).isdigit() and int(a) >= hoje.year})         if todos_os_anos and not df.empty else (hoje.year, hoje.year + 1)
    for ano in anos:
        sub = df[df["DataReferencia"] == str(ano)].sort_values("Data") if not df.empty else df
        if sub.empty:
            continue
        sub = sub.drop_duplicates("Data", keep="last")
        saida[str(ano)] = {"datas": sub["Data"].tolist(), "valores": [round(float(v), 4) for v in sub["Mediana"]]}
    return saida


URL_SIDRA_DESEMPREGO = "https://apisidra.ibge.gov.br/values/t/6381/n1/all/v/4099/p/all"
SGS_DESEMPREGO = 24369  # reserva: a mesma taxa da PNAD Contínua, republicada pelo Banco Central


def baixar_desemprego():
    """Taxa de desocupação da PNAD Contínua (trimestre móvel), direto do IBGE; o Banco Central fica de reserva.

    Cada ponto é datado pelo último mês do trimestre móvel (ex.: jul-ago-set/2026 -> 2026-09-01)."""
    try:
        linhas = requests.get(URL_SIDRA_DESEMPREGO, timeout=90).json()[1:]
        serie = pd.Series({pd.Timestamp(int(l["D3C"][:4]), int(l["D3C"][4:]), 1): float(l["V"])
                           for l in linhas if l.get("V") not in (None, "", "...", "-")}).sort_index()
        if len(serie) < 100:
            raise ValueError(f"IBGE devolveu só {len(serie)} pontos")
        return serie, "IBGE"
    except Exception as e:
        print("   ⚠️ desemprego pelo IBGE falhou, usando o Banco Central:", repr(e)[:120])
        return baixar_sgs(SGS_DESEMPREGO), "Banco Central (SGS 24369)"


def _regrediu(nova, antiga, compactada=False):
    """Série baixada menor que a publicada antes (começo, fim ou pontos a menos) indica resposta incompleta da API."""
    if not antiga or not antiga["datas"]:
        return None
    if nova.empty:
        return "a API devolveu a série vazia"
    ini, fim = nova.index[0].strftime("%Y-%m-%d"), nova.index[-1].strftime("%Y-%m-%d")
    if ini > antiga["datas"][0] or fim < antiga["datas"][-1]:
        return f"série veio de {ini} a {fim}, menor que a publicada ({antiga['datas'][0]} a {antiga['datas'][-1]})"
    if not compactada and len(nova) < len(antiga["datas"]):
        return f"série veio com {len(nova)} pontos, menos que os {len(antiga['datas'])} publicados"
    return None


def gerar():
    # Uma série que falhar fica com a versão publicada anteriormente (as outras seguem atualizadas)
    anterior = DIR_DADOS_SITE / "macro.json"
    anteriores = json.loads(anterior.read_text(encoding="utf-8"))["series"] if anterior.exists() else {}
    brutas, falhas = {}, []
    for chave, (codigo, _, _) in SERIES.items():
        try:
            nova = baixar_sgs(codigo)
            problema = _regrediu(nova, anteriores.get(chave), compactada=(chave == "selic_meta"))
            if problema:
                raise RuntimeError(problema)
            brutas[chave] = nova
        except Exception as e:
            if chave not in anteriores:
                raise
            falhas.append(f"{chave}: {e}")
            antiga = anteriores[chave]
            brutas[chave] = pd.Series(antiga["valores"], index=pd.to_datetime(antiga["datas"]), dtype=float)
    try:
        nova, fonte_desemprego = baixar_desemprego()
        problema = _regrediu(nova, anteriores.get("desemprego"))
        if problema:
            raise RuntimeError(problema)
        brutas["desemprego"] = nova
    except Exception as e:
        if "desemprego" not in anteriores:
            raise
        falhas.append(f"desemprego: {e}")
        antiga, fonte_desemprego = anteriores["desemprego"], "versão anterior"
        brutas["desemprego"] = pd.Series(antiga["valores"], index=pd.to_datetime(antiga["datas"]), dtype=float)
    for f in falhas:
        print("   ⚠️ mantida a versão anterior —", f)
    # A Selic meta só muda nas reuniões do Copom: guarda só os pontos de mudança (gráfico em degraus)
    selic = brutas["selic_meta"]
    brutas["selic_meta"] = pd.concat([selic[selic.diff() != 0], selic.iloc[[-1]]]).pipe(lambda s: s[~s.index.duplicated()])
    saida = {chave: _empacotar(brutas[chave], nome, un) for chave, (_, nome, un) in SERIES.items()}

    saida["ipca_12m"] = _empacotar(acumulado_12m(brutas["ipca"]).dropna(), "IPCA acumulado em 12 meses", "%")
    saida["desemprego"] = _empacotar(brutas["desemprego"], f"Taxa de desocupação (PNAD Contínua, trimestre móvel) — {fonte_desemprego}", "%")
    saida["igpm_12m"] = _empacotar(acumulado_12m(brutas["igpm"]).dropna(), "IGP-M acumulado em 12 meses", "%")
    saida["incc_12m"] = _empacotar(acumulado_12m(brutas["incc"]).dropna(), "INCC-DI acumulado em 12 meses", "%")

    # Média dos 5 núcleos acompanhados pelo Copom (calculada aqui, mês a mês)
    nucleos = pd.concat([brutas[k] for k in NUCLEOS_MEDIA], axis=1).dropna()
    brutas["nucleos_media"] = nucleos.mean(axis=1)
    saida["nucleos_media"] = _empacotar(brutas["nucleos_media"], "Média dos 5 núcleos (EX0, EX3, MS, DP, P55)", "% a.m.")
    for k in [*SERIES_NUCLEOS, "nucleos_media"]:
        saida[f"{k}_12m"] = _empacotar(acumulado_12m(brutas[k]).dropna(), f"{saida[k]['nome']} — 12 meses", "%")
    for k in ["ipca", "igpm", "incc", "nucleos_media", *SERIES_NUCLEOS]:
        saida[f"{k}_mm3"] = _empacotar(mm3_anualizada(brutas[k]).dropna(), f"{saida[k]['nome']} — média de 3 meses anualizada", "% a.a.")

    pib = brutas["pib_indice"]
    saida["pib_tri"] = _empacotar(((pib / pib.shift(1) - 1) * 100).dropna(), "PIB, variação trimestral dessazonalizada", "%")

    # Juro real ex-post: Selic meta no fim de cada mês descontado do IPCA 12 meses
    # usa a Selic diária (antes de guardar só as mudanças): meses sem reunião do Copom também entram
    selic_mes = selic.resample("MS").last().ffill()
    ipca12 = acumulado_12m(brutas["ipca"])
    juntos = pd.concat([selic_mes, ipca12], axis=1, keys=["selic", "ipca"]).dropna()
    real = ((1 + juntos["selic"] / 100) / (1 + juntos["ipca"] / 100) - 1) * 100
    saida["juro_real"] = _empacotar(real, "Juro real ex-post (Selic meta ÷ IPCA 12m)", "% a.a.")

    # Acumulado em 4 trimestres (como o IBGE divulga): soma dos últimos 4 trimestres sobre os 4 anteriores
    obs = brutas["pib_indice_obs"]
    saida["pib_12m"] = _empacotar(((obs.rolling(4).sum() / obs.rolling(4).sum().shift(4) - 1) * 100).dropna(),
                                  "PIB acumulado em 4 trimestres (12 meses)", "%")
    ibc = brutas["ibcbr_dessaz"]
    saida["ibcbr_mensal"] = _empacotar(((ibc / ibc.shift(1) - 1) * 100).dropna(), "IBC-Br, variação mensal dessazonalizada", "%")
    ibc_obs = brutas["ibcbr"]
    saida["ibcbr_12m"] = _empacotar(((ibc_obs.rolling(12).sum() / ibc_obs.rolling(12).sum().shift(12) - 1) * 100).dropna(),
                                    "IBC-Br acumulado em 12 meses", "%")

    # Contas públicas: cada série que falhar fica com a versão anterior (ou some, se nunca foi baixada)
    for chave, (codigo, nome, un) in SERIES_FISCAIS.items():
        try:
            nova = baixar_sgs(codigo)
            problema = _regrediu(nova, anteriores.get(chave))
            if problema:
                raise RuntimeError(problema)
            saida[chave] = _empacotar(nova, nome, un)
        except Exception as e:
            falhas.append(f"{chave}: {e}")
            print("   ⚠️ contas públicas —", chave, e)
            if chave in anteriores:
                saida[chave] = anteriores[chave]
    # IPCA e demais índices de preços (NTN-B): o BC não publica a participação numa série própria; vem por diferença
    outras = ["dmf_selic", "dmf_pre", "dmf_cambio", "dmf_tr", "dmf_igpm", "dmf_igpdi", "dmf_tjlp", "dmf_outros"]
    if all(k in saida for k in outras):
        partes = pd.concat([pd.Series(saida[k]["valores"], index=pd.to_datetime(saida[k]["datas"]), dtype=float) for k in outras], axis=1).dropna()
        ipca_dmf = (100 - partes.sum(axis=1)).clip(lower=0)
        saida["dmf_ipca"] = _empacotar(ipca_dmf[partes.index >= "2003-01-01"].round(2),
                                       "Dívida mobiliária federal — participação IPCA (por diferença: 100% − demais indexadores)", "%")

    focus = {chave: baixar_focus(nome, todos_os_anos=(chave == "selic")) for chave, nome in FOCUS.items()}
    arquivo = DIR_DADOS_SITE / "macro.json"
    arquivo.write_text(json.dumps({"gerado_em": date.today().isoformat(), "series": saida, "focus": focus, "falhas": falhas},
                                  ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return arquivo


if __name__ == "__main__":
    caminho = gerar()
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    for k, s in dados["series"].items():
        print(f"{k:12s} {len(s['datas']):6d} pontos  último {s['datas'][-1] if s['datas'] else '-'} = {s['valores'][-1] if s['valores'] else '-'} {s['unidade']}")
    for k, f in dados["focus"].items():
        print("focus", k, {ano: (v["datas"][-1], v["valores"][-1]) for ano, v in f.items()})
    print(f"{caminho} ({caminho.stat().st_size // 1024} KB)")
