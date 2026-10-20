"""
screening.py — Coleta dados fundamentalistas da CVM para TODAS as empresas
de uma vez (em vez de uma busca por empresa), para montar uma tabela-resumo
de todo o universo de não-financeiras.

Diferença chave pra cvm_itr.py: lá cada busca filtra 1 CNPJ de dentro do CSV
completo; aqui o CSV é lido uma única vez e todas as empresas relevantes
saem numa mesma passada — é a única forma viável de cobrir ~600 empresas
sem levar horas (senão seria reler o mesmo arquivo de ~150MB centenas de vezes).

Simplificações conscientes da v1 (documentadas, não escondidas):
- Receita/Lucro/Margens usam o ÚLTIMO ANO FISCAL COMPLETO (DFP), não um LTM
  trimestral — mais simples de calcular pra ~600 empresas de uma vez, e
  totalmente razoável pra um investidor de longo prazo (o que importa é a
  tendência anual, não o trimestre isolado mais recente).
- Ativo/Passivo/PL usam o balanço mais recente disponível (ITR do ano corrente).
- Market cap = preço de cada classe (ON/PN) × ações em circulação DAQUELA
  classe — nunca soma o "marketCap" pronto do yfinance (que só reflete uma
  classe) nem usa a quantidade de ações da composição de capital da CVM.
  Essa última foi testada e descartada: o campo QT_ACAO_* vem em unidades
  inconsistentes entre empresas sem nenhum indicador no arquivo pra saber
  qual é qual (WEG e Petrobras reportam a contagem cheia; Vale e Itaú
  reportam 1000x menor, aparentemente em milhares) — usar isso sem
  validação geraria P/L e P/VP completamente errados pra várias empresas.
  O sharesOutstanding do yfinance por ticker individual foi validado como
  confiável mesmo em empresas com ON+PN (o problema do yfinance é só a
  soma/"marketCap" agregado, não a contagem de ações de cada classe isolada).
- Units (ex: papel "11") entram como aproximação (preço da unit × ações em
  circulação da unit), só quando não há ON/PN cotados separadamente.
"""

import time
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd

from config.config import RAW_DIR
from src.cvm_itr import baixar_zip_ano, baixar_cadastro


def ler_contas_todas_empresas(ano: int, sigla: str, tipo: str, cd_contas: set, fonte: str = "ITR") -> pd.DataFrame:
    """
    Lê uma demonstração (ex: BPA_con) do ZIP anual da CVM e retorna, para
    TODAS as empresas, só as linhas cujo CD_CONTA está em cd_contas.

    Args:
        ano:       ano de referência
        sigla:     BPA, BPP, DRE ou DFC_MI
        tipo:      "con" ou "ind"
        cd_contas: conjunto de códigos de conta a manter (ex: {"1", "1.01"})
        fonte:     "ITR" ou "DFP"
    Returns:
        DataFrame com CNPJ_CIA, DENOM_CIA, CD_CONTA, DT_INI_EXERC (se houver),
        DT_FIM_EXERC, DT_REFER, VERSAO, VL_CONTA — de todas as empresas, com
        VL_CONTA já convertido pra reais cheios (ver nota sobre ESCALA_MOEDA)
    """
    prefixo = "itr" if fonte == "ITR" else "dfp"
    caminho_zip = baixar_zip_ano(ano, fonte)
    nome_csv = f"{prefixo}_cia_aberta_{sigla}_{tipo}_{ano}.csv"

    with zipfile.ZipFile(caminho_zip) as z:
        if nome_csv not in z.namelist():
            return pd.DataFrame()

        partes = []
        with z.open(nome_csv) as f:
            leitor = pd.read_csv(
                f, sep=";", encoding="latin1", decimal=".",
                dtype={"CNPJ_CIA": str, "CD_CONTA": str}, chunksize=200_000,
            )
            for bloco in leitor:
                partes.append(bloco[bloco["CD_CONTA"].isin(cd_contas)])

    df = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
    if df.empty:
        return df

    # ESCALA_MOEDA varia por empresa ("MIL" ou "UNIDADE") — sem converter pra
    # reais cheios aqui, cruzar com o market cap (que é sempre reais cheios,
    # vindo do preço × ações do yfinance) dá P/L e P/VP fora da realidade.
    multiplicador = df["ESCALA_MOEDA"].map({"MIL": 1000, "UNIDADE": 1}).fillna(1)
    df["VL_CONTA"] = df["VL_CONTA"] * multiplicador
    return df


CAMINHO_EMPRESAS_SELECIONADAS = Path(__file__).resolve().parent.parent / "config" / "empresas_selecionadas.csv"


def universo_selecionado() -> pd.DataFrame:
    """
    Universo do projeto: a lista curada à mão em config/empresas_selecionadas.csv
    (CNPJ_CIA;Empresa;Tickers), com os tickers de cada classe exatamente como
    definidos ali. Substitui o filtro automático antigo (lista da B3 + setores):
    quem decide quais empresas e quais tickers entram é essa lista.

    O cadastro da CVM entra só pra trazer o setor de atividade.
    Retorna: CNPJ_CIA, DENOM_SOCIAL (nome da lista), SETOR_ATIV, tickers_lista (list[str]).
    """
    lista = pd.read_csv(CAMINHO_EMPRESAS_SELECIONADAS, sep=";", dtype=str, encoding="utf-8")
    cad = pd.read_csv(baixar_cadastro(), sep=";", encoding="latin1", dtype=str)
    setor_por_cnpj = cad.drop_duplicates("CNPJ_CIA").set_index("CNPJ_CIA")["SETOR_ATIV"]

    df = pd.DataFrame({
        "CNPJ_CIA": lista["CNPJ_CIA"],
        "DENOM_SOCIAL": lista["Empresa"],
        "SETOR_ATIV": lista["CNPJ_CIA"].map(setor_por_cnpj),
        "tickers_lista": [[t.strip() for t in x.split("/")] for x in lista["Tickers"]],
    })
    return df.sort_values("DENOM_SOCIAL").reset_index(drop=True)


CAMINHO_BANCOS_LISTADOS = Path(__file__).resolve().parent.parent / "config" / "bancos_listados.csv"


def universo_perfis() -> pd.DataFrame:
    """Lista de empresas + bancos listados: usada só nos perfis (FRE/FCA, fatos relevantes, cotação e proventos).

    Os bancos não entram no padrão de demonstrações das empresas não financeiras (vêm do IF.data do
    Banco Central, em pipeline.bancos)."""
    empresas = universo_selecionado()
    lista = pd.read_csv(CAMINHO_BANCOS_LISTADOS, sep=";", dtype=str, encoding="utf-8")
    bancos = pd.DataFrame({
        "CNPJ_CIA": lista["CNPJ_CIA"], "DENOM_SOCIAL": lista["Empresa"], "SETOR_ATIV": "Bancos",
        "tickers_lista": [[t.strip() for t in x.split("/")] for x in lista["Tickers"]],
    })
    bancos = bancos[~bancos["CNPJ_CIA"].isin(empresas["CNPJ_CIA"])]
    return pd.concat([empresas, bancos], ignore_index=True)


def _ultimo_valor_por_empresa(bruto: pd.DataFrame, cd_conta: str) -> pd.Series:
    """De um DataFrame já filtrado por CD_CONTA, pega o valor mais recente (maior DT_FIM_EXERC) por empresa."""
    if bruto.empty:
        return pd.Series(dtype=float)
    sub = bruto[bruto["CD_CONTA"] == cd_conta].copy()
    if sub.empty:
        return pd.Series(dtype=float)
    sub = sub.sort_values(["CNPJ_CIA", "DT_FIM_EXERC", "VERSAO"])
    sub = sub.drop_duplicates(subset="CNPJ_CIA", keep="last")
    return sub.set_index("CNPJ_CIA")["VL_CONTA"]


def coletar_fundamentos(ano_fiscal: int = None) -> pd.DataFrame:
    """
    Monta a tabela fundamentalista de todas as empresas do universo não
    financeiro: balanço mais recente (ITR do ano corrente) + DRE dos últimos
    2 anos fiscais completos (DFP), pra calcular margem e crescimento.

    Args:
        ano_fiscal: último ano fiscal completo a usar (default: ano corrente - 1)
    Returns:
        DataFrame indexado por CNPJ_CIA com as contas brutas (sem indicador calculado ainda)
    """
    ano_atual = date.today().year
    ano_fiscal = ano_fiscal or (ano_atual - 1)
    ano_anterior = ano_fiscal - 1

    universo = universo_selecionado()
    print(f"📋 Universo: {len(universo)} empresas (lista selecionada)")

    def _con_e_ind(ano, sigla, cd_contas, fonte="ITR"):
        con = ler_contas_todas_empresas(ano, sigla, "con", cd_contas, fonte)
        ind = ler_contas_todas_empresas(ano, sigla, "ind", cd_contas, fonte)
        return con, ind

    def _valor_com_fallback(con, ind, cd_conta):
        # Consolidado zerado conta como ausente: a TIM publicou o DFP 2025 consolidado com
        # receita e lucro 0, mas o individual traz os valores reais.
        consolidado = _ultimo_valor_por_empresa(con, cd_conta)
        return consolidado.where(consolidado != 0).combine_first(_ultimo_valor_por_empresa(ind, cd_conta))

    print("🔎 Balanço (posição mais recente)...")
    bpa_con, bpa_ind = _con_e_ind(ano_atual, "BPA", {"1", "1.01"})
    bpp_con, bpp_ind = _con_e_ind(ano_atual, "BPP", {"2", "2.01", "2.03"})

    print(f"🔎 DRE — ano fiscal {ano_fiscal}...")
    dre_atual_con, dre_atual_ind = _con_e_ind(ano_fiscal, "DRE", {"3.01", "3.03", "3.11"}, fonte="DFP")
    print(f"🔎 DRE — ano fiscal {ano_anterior} (comparação)...")
    dre_ant_con, dre_ant_ind = _con_e_ind(ano_anterior, "DRE", {"3.01", "3.03", "3.11"}, fonte="DFP")

    tabela = universo.set_index("CNPJ_CIA").copy()
    tabela["ativo_total"] = _valor_com_fallback(bpa_con, bpa_ind, "1")
    tabela["ativo_circulante"] = _valor_com_fallback(bpa_con, bpa_ind, "1.01")
    tabela["passivo_total"] = _valor_com_fallback(bpp_con, bpp_ind, "2")
    tabela["passivo_circulante"] = _valor_com_fallback(bpp_con, bpp_ind, "2.01")
    tabela["patrimonio_liquido"] = _valor_com_fallback(bpp_con, bpp_ind, "2.03")

    tabela["receita"] = _valor_com_fallback(dre_atual_con, dre_atual_ind, "3.01")
    tabela["lucro_bruto"] = _valor_com_fallback(dre_atual_con, dre_atual_ind, "3.03")
    tabela["lucro_liquido"] = _valor_com_fallback(dre_atual_con, dre_atual_ind, "3.11")
    tabela["receita_ano_anterior"] = _valor_com_fallback(dre_ant_con, dre_ant_ind, "3.01")
    tabela["lucro_liquido_ano_anterior"] = _valor_com_fallback(dre_ant_con, dre_ant_ind, "3.11")

    tabela.attrs["ano_fiscal"] = ano_fiscal
    tabela.attrs["ano_anterior"] = ano_anterior
    return tabela.reset_index()


def resolver_tickers(tabela: pd.DataFrame) -> pd.DataFrame:
    """
    Separa os tickers da lista selecionada por classe: ON (final 3), Unit (final 11)
    e PN/preferenciais (4, 5, 6...). Uma empresa pode ter qualquer combinação.
    """
    def _classe(t):
        sufixo = t[4:]
        return "unit" if sufixo == "11" else "on" if sufixo == "3" else "pn"

    tabela = tabela.copy()
    tickers = tabela["tickers_lista"]
    tabela["tickers_candidatos"] = tickers
    for classe in ("on", "pn", "unit"):
        tabela[f"ticker_{classe}"] = [" / ".join(t for t in c if _classe(t) == classe) or None for c in tickers]
    return tabela


def _dados_mercado_ticker(ticker: str) -> dict:
    """
    Preço, ações em circulação, volume médio (30d) e dividendos dos últimos
    12 meses, via yfinance.

    Usa info["sharesOutstanding"] (ações em circulação DAQUELA classe/ticker
    específico) em vez da composição de capital da CVM — descobrimos que esse
    campo da CVM vem em unidades inconsistentes entre empresas (algumas em
    unidade cheia, outras em milhares, sem indicador no arquivo pra saber
    qual é qual — ex: WEG e Petrobras vêm corretas, Vale e Itaú vêm 1000x
    menores).

    Importante: usar fast_info["shares"] em vez de info["sharesOutstanding"]
    parece equivalente mas NÃO é — testamos e, pra empresas com ON+PN, o
    fast_info.shares vem como um número "implícito" agregado (ex: Petrobras
    retornou o mesmo valor grande nas duas classes, inflando o market cap
    pra mais que o dobro do real). O info["sharesOutstanding"] tradicional,
    por outro lado, já foi validado como correto por classe mesmo em
    empresas com ON+PN — é mais lento (endpoint mais pesado), mas é o único
    dos dois que dá o número certo por ticker individual.
    """
    import yfinance as yf

    try:
        t = yf.Ticker(f"{ticker}.SA")
        info = t.info
        preco = float(info.get("currentPrice") or info.get("regularMarketPrice") or t.fast_info["last_price"])
        acoes_em_circulacao = float(info["sharesOutstanding"])

        hist = t.history(period="3mo")
        volume_medio = float(hist["Volume"].tail(30).mean()) if not hist.empty else 0.0

        divs = t.dividends
        dividendos_12m = 0.0
        if not divs.empty:
            limite = pd.Timestamp.now(tz=divs.index.tz) - pd.Timedelta(days=365)
            dividendos_12m = float(divs[divs.index >= limite].sum())

        return {
            "preco": preco, "acoes_em_circulacao": acoes_em_circulacao,
            "acoes_totais_empresa": float(info.get("impliedSharesOutstanding") or 0),
            "volume_medio_30d": volume_medio, "dividendos_12m": dividendos_12m,
        }
    except Exception as e:
        print(f"   ⚠️ {ticker}: erro ao buscar no yfinance ({e})")
        return {}


def buscar_dados_mercado(tabela: pd.DataFrame, pausa: float = 0.3) -> pd.DataFrame:
    """
    Busca preço/ações em circulação/volume/dividendos no yfinance pra cada
    ticker (ON, PN, Unit) da tabela. Market cap = soma, por classe existente,
    de preço × ações em circulação DAQUELA classe (via yfinance) — nunca usa
    o "marketCap" pronto do yfinance (que só reflete uma classe) nem a
    quantidade de ações da CVM (que descobrimos ser inconsistente em escala).

    Args:
        tabela: saída de resolver_tickers()
        pausa:  segundos de espera entre cada empresa (educação com o servidor)
    """
    tabela = tabela.copy()
    cache_ticker = {}
    n = len(tabela)

    market_cap, preco_referencia, dividendos_12m, volume_medio = [], [], [], []

    def _consultar(ticker):
        if ticker not in cache_ticker:
            cache_ticker[ticker] = _dados_mercado_ticker(ticker)
            time.sleep(pausa)
        return cache_ticker[ticker]

    for i, row in enumerate(tabela.itertuples(), start=1):
        if i % 25 == 0 or i == n:
            print(f"   📈 {i}/{n} empresas consultadas no yfinance...")

        candidatos = list(row.tickers_candidatos)
        classes_on_pn = [t for t in candidatos if not t.endswith("11")]
        units = [t for t in candidatos if t.endswith("11")]

        achados = {t: _consultar(t) for t in classes_on_pn}
        achados = {t: d for t, d in achados.items() if d}

        units_apenas = False
        # Sem ON nem PN cotados — tenta a Unit como aproximação
        if not achados:
            units_apenas = True
            achados = {t: d for t in units if (d := _consultar(t))}
            # Várias units: soma seria dupla contagem do mesmo capital, fica só a mais líquida
            if len(achados) > 1:
                melhor = max(achados, key=lambda t: achados[t]["volume_medio_30d"])
                achados = {melhor: achados[melhor]}

        cap_total = sum(d["preco"] * d["acoes_em_circulacao"] for d in achados.values())
        if achados and not units_apenas:
            # Classes sem cotação (ex: a ON da Raízen, nas mãos dos controladores, ou a CEEB6)
            # não entram na soma acima: o total de ações da empresa (impliedSharesOutstanding)
            # inclui todas elas. As que faltam são valoradas ao preço médio das classes cotadas.
            acoes_cotadas = sum(d["acoes_em_circulacao"] for d in achados.values())
            # o Yahoo devolve totais diferentes por ticker da mesma empresa (PETR4 > PETR3);
            # o menor positivo é o conservador e bate com a soma das classes quando está completa
            totais = [d["acoes_totais_empresa"] for d in achados.values() if d["acoes_totais_empresa"] > 0]
            total_empresa = min(totais) if totais else 0
            faltam = total_empresa - acoes_cotadas
            if faltam > 0.02 * total_empresa:
                cap_total += faltam * cap_total / acoes_cotadas

        if achados:
            # Preço e dividendos vêm da classe mais líquida (somar dividendos de ON+PN e dividir
            # por um preço só dobraria o yield); market cap e volume somam todas as classes
            ref = max(achados.values(), key=lambda d: d["volume_medio_30d"])
            market_cap.append(cap_total or None)
            preco_referencia.append(ref["preco"])
            dividendos_12m.append(ref["dividendos_12m"])
            volume_medio.append(sum(d["volume_medio_30d"] for d in achados.values()))
        else:
            market_cap.append(None)
            preco_referencia.append(None)
            dividendos_12m.append(None)
            volume_medio.append(None)

    tabela["preco"] = preco_referencia
    tabela["market_cap"] = market_cap
    tabela["dividendos_12m_por_acao"] = dividendos_12m
    tabela["volume_medio_30d"] = volume_medio

    return tabela


def calcular_indicadores(tabela: pd.DataFrame) -> pd.DataFrame:
    """Calcula os indicadores finais de screening a partir dos dados brutos já coletados."""
    tabela = tabela.copy()

    receita = tabela["receita"]
    tabela["margem_bruta_pct"] = tabela["lucro_bruto"] / receita * 100
    tabela["margem_liquida_pct"] = tabela["lucro_liquido"] / receita * 100
    tabela["crescimento_receita_pct"] = (receita / tabela["receita_ano_anterior"] - 1) * 100
    tabela["roe_pct"] = tabela["lucro_liquido"] / tabela["patrimonio_liquido"] * 100
    tabela["liquidez_corrente"] = tabela["ativo_circulante"] / tabela["passivo_circulante"]

    tabela["p_l"] = tabela["market_cap"] / tabela["lucro_liquido"]
    tabela["p_vp"] = tabela["market_cap"] / tabela["patrimonio_liquido"]
    tabela["dividend_yield_pct"] = tabela["dividendos_12m_por_acao"] / tabela["preco"] * 100

    # Divisão por lucro/PL zero vira infinito; no screening isso é "sem dado".
    return tabela.replace([float("inf"), float("-inf")], float("nan"))


def montar_screening(ano_fiscal: int = None, pausa_yfinance: float = 0.3) -> pd.DataFrame:
    """Orquestra o pipeline inteiro: fundamentos (CVM) → tickers (lista selecionada) → mercado (yfinance) → indicadores."""
    tabela = coletar_fundamentos(ano_fiscal)
    tabela = resolver_tickers(tabela)
    print(f"📈 Buscando preço/dividendos/volume no yfinance para {len(tabela)} empresas...")
    tabela = buscar_dados_mercado(tabela, pausa=pausa_yfinance)
    tabela = calcular_indicadores(tabela)

    # A lista é curada à mão, então empresa sem cotação no Yahoo NÃO sai do resultado
    # (fica com preço/market cap vazios; o dashboard esconde essas por padrão).
    sem_preco = tabela[tabela["preco"].isna()]
    print(f"⚠️ {len(sem_preco)} empresas da lista sem preço no yfinance: {', '.join(sem_preco['ticker_on'].fillna(sem_preco['ticker_pn']).fillna(sem_preco['ticker_unit']).astype(str))}")

    return tabela
