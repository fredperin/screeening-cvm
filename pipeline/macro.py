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

from config.config import RAW_DIR
from pipeline import DIR_DADOS_SITE

URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial={ini}&dataFinal={fim}"
URL_FOCUS = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais"
INICIO = 2000
DIR_SGS = RAW_DIR / "sgs"  # cópia local das séries brutas (guardada no cache do GitHub Actions)
DIR_SGS.mkdir(parents=True, exist_ok=True)
REVISAO_SGS_ANOS = 3    # janela baixada nos dias comuns: cobre as revisões que o BC faz nas séries
COMPLETA_SGS_DIAS = 7   # série inteira de novo uma vez por semana (o comparador de versões confere a diferença)

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
    """Série desde `inicio`, com cópia local (data/raw/sgs): nos dias comuns baixa só os últimos
    REVISAO_SGS_ANOS anos e junta ao histórico guardado (as revisões do BC caem dentro dessa janela);
    a cada COMPLETA_SGS_DIAS dias, sem cópia ou se o pedaço novo não se encaixar, baixa a série inteira."""
    hoje = date.today()
    arq = DIR_SGS / f"{codigo}_{inicio}.json"
    try:
        guardada = json.loads(arq.read_text(encoding="utf-8"))
        antiga = pd.Series(guardada["valores"], index=pd.to_datetime(guardada["datas"]), dtype=float)
        idade = (hoje - date.fromisoformat(guardada["completa_em"])).days
    except (OSError, ValueError, KeyError):
        antiga, idade = None, None

    def guardar(serie, completa_em):
        arq.write_text(json.dumps({"completa_em": completa_em, "datas": [d.strftime("%Y-%m-%d") for d in serie.index],
                                   "valores": [float(v) for v in serie.values]}), encoding="utf-8")

    if antiga is not None and not antiga.empty and idade < COMPLETA_SGS_DIAS:
        corte = date(hoje.year - REVISAO_SGS_ANOS, 1, 1)
        if corte.year > inicio:
            recente = _baixar_sgs_janelas(codigo, corte.year, janela)
            # série encerrada (nada novo na janela) fica como está; pedaço novo precisa encostar no histórico guardado
            if recente.empty and antiga.index[-1] < pd.Timestamp(corte):
                return antiga
            if not recente.empty and recente.index[0] <= antiga.index[-1] + pd.Timedelta(days=400):
                serie = pd.concat([antiga[antiga.index < pd.Timestamp(corte)], recente])
                serie = serie[~serie.index.duplicated(keep="last")].sort_index()
                guardar(serie, guardada["completa_em"])
                return serie
    serie = _baixar_sgs_janelas(codigo, inicio, janela)
    if not serie.empty:
        guardar(serie, hoje.isoformat())
    return serie


def _baixar_sgs_janelas(codigo, inicio=INICIO, janela=10):
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


# ---------------- Conjuntura (protótipo das sugestões de 2026-11-14) ----------------
# Séries do Banco Central conferidas por valor; as marcadas "a confirmar" precisam ter o nome conferido no SGS antes de ir ao ar
SERIES_CONJUNTURA = {
    "ipca_servicos": (10844, "IPCA — serviços", "% a.m."),
    "ipca_livres": (11428, "IPCA — itens livres", "% a.m."),
    "ipca_administrados": (4449, "IPCA — preços monitorados (administrados) [a confirmar]", "% a.m."),
    "ipca_industriais": (27863, "IPCA — bens industriais [a confirmar]", "% a.m."),
    "ipca_alimentos_dom": (27864, "IPCA — alimentação no domicílio [a confirmar]", "% a.m."),
    "ipca_difusao": (21379, "IPCA — índice de difusão", "% dos itens"),
    "cambio_real": (11752, "Taxa de câmbio real efetiva (índice)", "índice"),
    "icbr": (27574, "Índice de Commodities Brasil (IC-Br), em reais", "índice"),
    "icbr_agro": (27575, "IC-Br — agropecuária", "índice"),
    "icbr_metal": (27576, "IC-Br — metal", "índice"),
    "icbr_energia": (27577, "IC-Br — energia", "índice"),
    "caged_estoque": (28763, "Emprego formal — estoque de vínculos (Novo Caged)", "vínculos"),
    "ibcbr_agro": (29601, "IBC-Br — agropecuária (observado)", "índice"),
    "ibcbr_industria": (29603, "IBC-Br — indústria (observado)", "índice"),
    "ibcbr_servicos": (29605, "IBC-Br — serviços (observado)", "índice"),
    "renda_familias": (29027, "Renda disponível bruta das famílias, real (IPCA), dessazonalizada", "R$ milhões"),
}
SIDRA_CONJUNTURA = {  # IBGE (SIDRA), índices com ajuste sazonal (2022=100)
    "pim": ("t/8888/n1/all/v/12607/p/all/c544/129314", "Produção industrial — indústria geral (PIM-PF, dessaz.)"),
    "pmc": ("t/8880/n1/all/v/7170/p/all/c11046/56734", "Vendas no varejo — volume (PMC, dessaz.)"),
    "pms": ("t/5906/n1/all/v/7168/p/all/c11046/56726", "Volume de serviços (PMS, dessaz.)"),
}
URL_FOCUS_12M = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoInflacao12Meses"


def _sidra(caminho):
    import re
    dados = _get(f"https://apisidra.ibge.gov.br/values/{caminho}")
    linhas = {}
    for r in dados[1:]:
        periodo = next((v for v in r.values() if isinstance(v, str) and re.fullmatch(r"\d{6}", v)), None)
        if periodo and r.get("V") not in (None, "...", "-", "X"):
            linhas[pd.Timestamp(int(periodo[:4]), int(periodo[4:]), 1)] = float(r["V"])
    return pd.Series(linhas).sort_index()


def _focus_ipca_12m():
    filtro = "Indicador eq 'IPCA' and Suavizada eq 'S' and baseCalculo eq 0"
    dados = _get(f"{URL_FOCUS_12M}?$filter={quote(filtro)}&$select=Data,Mediana&$format=json&$top=100000")
    df = pd.DataFrame(dados.get("value", []))
    s = pd.Series(df["Mediana"].astype(float).values, index=pd.to_datetime(df["Data"])).sort_index()
    return s[~s.index.duplicated(keep="last")]


def conjuntura(saida, brutas, anteriores, falhas):
    """Séries do painel de conjuntura e das abas de Atividade, Inflação, Monetária e Câmbio. Falha mantém a versão anterior."""
    def guardar(chave, serie, nome, un, casas=4):
        saida[chave] = _empacotar(serie.dropna(), nome, un, casas)

    def tentar(chave, funcao):
        try:
            funcao()
        except Exception as e:  # noqa: BLE001
            falhas.append(f"{chave}: {e}")
            print("   ⚠️ conjuntura —", chave, e)
            if chave in anteriores:
                saida[chave] = anteriores[chave]

    novas = {}
    for chave, (codigo, nome, un) in SERIES_CONJUNTURA.items():
        def baixar(chave=chave, codigo=codigo, nome=nome, un=un):
            novas[chave] = baixar_sgs(codigo)
            guardar(chave, novas[chave], nome, un)
        tentar(chave, baixar)
    for k in ("ipca_servicos", "ipca_livres", "ipca_administrados", "ipca_industriais", "ipca_alimentos_dom"):
        if k in novas:
            guardar(f"{k}_12m", acumulado_12m(novas[k]), f"{SERIES_CONJUNTURA[k][1]} — 12 meses", "%")
            guardar(f"{k}_mm3", mm3_anualizada(novas[k]), f"{SERIES_CONJUNTURA[k][1]} — 3 meses anualizado", "% a.a.")
    if "ipca_difusao" in novas:
        guardar("ipca_difusao_mm3", novas["ipca_difusao"].rolling(3).mean(), "IPCA — difusão, média de 3 meses", "% dos itens")
    if "caged_estoque" in novas:
        e = novas["caged_estoque"]
        guardar("caged_saldo", e.diff(), "Emprego formal — saldo do mês (variação do estoque)", "vínculos", 0)
        guardar("caged_12m", e.diff(12), "Emprego formal — saldo em 12 meses", "vínculos", 0)
    for k in ("ibcbr_agro", "ibcbr_industria", "ibcbr_servicos"):
        if k in novas:
            s = novas[k]
            guardar(f"{k}_12m", (s.rolling(12).sum() / s.rolling(12).sum().shift(12) - 1) * 100, f"{SERIES_CONJUNTURA[k][1]} — acumulado em 12 meses", "%")
    for k in ("icbr", "icbr_agro", "icbr_metal", "icbr_energia", "renda_familias", "cambio_real"):
        if k in novas:
            guardar(f"{k}_12m", (novas[k] / novas[k].shift(12) - 1) * 100, f"{SERIES_CONJUNTURA[k][1]} — variação em 12 meses", "%")
    for chave, (caminho, nome) in SIDRA_CONJUNTURA.items():
        def baixar_ibge(chave=chave, caminho=caminho, nome=nome):
            s = _sidra(caminho)
            guardar(chave, s, nome, "índice (2022=100)")
            guardar(f"{chave}_12m", (s / s.shift(12) - 1) * 100, f"{nome} — contra 12 meses antes", "%")
            guardar(f"{chave}_mm", (s / s.shift(1) - 1) * 100, f"{nome} — variação no mês", "%")
        tentar(chave, baixar_ibge)

    def juro_ex_ante():
        f12 = _focus_ipca_12m()
        guardar("focus_ipca_12m", f12.resample("MS").last(), "Focus — IPCA esperado nos próximos 12 meses (suavizado)", "%")
        selic = brutas["selic_meta"].resample("MS").last().ffill()
        juntos = pd.concat([selic, f12.resample("MS").last()], axis=1, keys=["selic", "exp"]).dropna()
        guardar("juro_real_exante", ((1 + juntos["selic"] / 100) / (1 + juntos["exp"] / 100) - 1) * 100,
                "Juro real ex-ante (Selic meta ÷ IPCA esperado 12 meses, Focus)", "% a.a.")
    tentar("juro_real_exante", juro_ex_ante)


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

    selic_diaria = selic  # (a Selic meta diária, antes de guardar só as mudanças)
    conjuntura(saida, {"selic_meta": selic_diaria}, anteriores, falhas)
    focus = {chave: baixar_focus(nome, todos_os_anos=True) for chave, nome in FOCUS.items()}  # todos os anos que o Focus projeta
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
