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

import base64
import json
import time
import zipfile
from datetime import date

import pandas as pd
import requests

from config.config import RAW_DIR
from src.cvm_itr import baixar_zip_ano, baixar_cadastro, _baixar_zip_fca, _normalizar_cnpj

URL_LISTA_B3 = "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/GetInitialCompanies/{}"

SETORES_FINANCEIROS = [
    "Bancos", "Intermediação Financeira", "Seguradoras", "Arrendamento Mercantil",
    "Crédito Imobiliário", "Bolsas de Valores", "Factoring", "Securitização de Recebíveis",
]


def _baixar_lista_b3(forcar: bool = False) -> pd.DataFrame:
    """
    Baixa a lista oficial de empresas da B3 (API pública por trás de
    sistemaswebb3-listados.b3.com.br/listedCompaniesPage), paginando até o fim.

    Isso é diferente do cadastro da CVM: a CVM registra ~3x mais "companhias
    abertas" do que realmente tem ação negociando na bolsa — securitizadoras,
    holdings de capital fechado que só emitem dívida, etc. também são
    "Categoria A" e "BOLSA" no cadastro da CVM, mas nunca tiveram uma ação
    de fato listada. Essa lista da B3 é o cruzamento que resolve isso: só
    quem tem type="1" aqui é uma ação brasileira genuinamente negociada.
    """
    caminho = RAW_DIR / "b3_empresas_listadas.json"
    if caminho.exists() and not forcar:
        idade_dias = (time.time() - caminho.stat().st_mtime) / 86400
        if idade_dias < 7:
            print(f"📁 Usando cache: {caminho}")
            # dtype=str é essencial aqui: sem isso, o pandas infere "type" e
            # "cnpj" como número ao reler o JSON, e a comparação de string
            # com "1" (ou o zfill do CNPJ) para de bater com qualquer linha.
            return pd.read_json(caminho, dtype=str)

    print("📥 Baixando lista de empresas listadas na B3...")
    todos = []
    pagina = 1
    while True:
        params = {"language": "pt-br", "pageNumber": pagina, "pageSize": 100}
        b64 = base64.b64encode(json.dumps(params).encode()).decode()
        resp = requests.get(URL_LISTA_B3.format(b64), headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        resp.raise_for_status()
        dados = resp.json()
        resultados = dados.get("results", [])
        if not resultados:
            break
        todos.extend(resultados)
        if pagina >= dados["page"]["totalPages"]:
            break
        pagina += 1
        time.sleep(0.15)

    df = pd.DataFrame(todos)
    df.to_json(caminho, orient="records", force_ascii=False)
    print(f"✅ {len(df)} registros salvos em {caminho}")
    return df


def raizes_cnpj_realmente_listadas_b3() -> set:
    """
    Raiz do CNPJ (8 primeiros dígitos — identifica o grupo/empresa, não a
    filial) de empresas com ações de fato negociadas na B3 (type="1" na API
    da B3 — exclui BDRs, ETPs, e as milhares de "companhias abertas" da CVM
    que nunca chegaram a listar uma ação).

    Por que raiz e não o CNPJ completo: a CVM às vezes cadastra a empresa sob
    um CNPJ (ex: filial matriz, ".../0001-XX") enquanto a B3 lista a ação sob
    outro CNPJ do mesmo grupo (ex: ".../0003-XX") — vimos isso na prática com
    a Tupy. Os 8 primeiros dígitos (a raiz) são estáveis entre filiais da
    mesma empresa, então comparar só por eles evita esse falso negativo.

    Limitação conhecida (não resolvida por CNPJ nenhum): empresas que
    mudaram de domicílio societário pra uma holding estrangeira mantêm o
    CNPJ antigo "vivo" no cadastro da CVM, mas a ação passa a ser negociada
    por uma entidade nova com CNPJ completamente diferente — ex: JBS SA (CNPJ
    brasileiro original) virou JBS N.V. (holding holandesa, outro CNPJ) após
    a redomiciliação pra dupla listagem em Nova York. Isso não tem como
    resolver comparando CNPJ; entra como exceção conhecida.
    """
    df = _baixar_lista_b3()
    df = df[df["type"] == "1"]
    cnpjs_completos = df["cnpj"].astype(str).str.zfill(14)
    return set(cnpjs_completos.str[:8])


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


def universo_nao_financeiro() -> pd.DataFrame:
    """
    Lista as companhias ATIVAS, negociadas em BOLSA, Categoria A (podem emitir
    ação), excluindo setores financeiros (plano de contas diferente — ver
    conversa anterior sobre bancos/seguradoras terem estrutura própria) — E
    cruzando com a lista oficial da B3 pra manter só quem tem ação de fato
    negociada (o cadastro da CVM sozinho superestima muito esse universo:
    ~2600 "companhias abertas" registradas nunca chegaram a listar uma ação).
    """
    caminho = baixar_cadastro()
    df = pd.read_csv(caminho, sep=";", encoding="latin1", dtype=str)

    df = df[(df["SIT"] == "ATIVO") & (df["TP_MERC"] == "BOLSA") & (df["CATEG_REG"] == "Categoria A")]
    padrao_financeiro = "|".join(SETORES_FINANCEIROS)
    df = df[~df["SETOR_ATIV"].str.contains(padrao_financeiro, case=False, na=False, regex=True)]

    raizes_b3 = raizes_cnpj_realmente_listadas_b3()
    df = df[df["CNPJ_CIA"].apply(_normalizar_cnpj).str[:8].isin(raizes_b3)]

    df = df.drop_duplicates(subset="CNPJ_CIA")[["CNPJ_CIA", "DENOM_SOCIAL", "SETOR_ATIV"]]
    return df.sort_values("DENOM_SOCIAL").reset_index(drop=True)


def ler_tickers_todas_empresas(ano: int) -> pd.DataFrame:
    """
    Lê o Formulário Cadastral (FCA) e retorna, para todas as empresas, os
    tickers negociados em Bolsa (código B3, ex: WEGE3), um por linha.
    """
    caminho_zip = _baixar_zip_fca(ano)
    nome_vm = f"fca_cia_aberta_valor_mobiliario_{ano}.csv"

    with zipfile.ZipFile(caminho_zip) as z:
        if nome_vm not in z.namelist():
            return pd.DataFrame()
        with z.open(nome_vm) as f:
            df = pd.read_csv(f, sep=";", encoding="latin1", dtype={"CNPJ_Companhia": str})

    return df[(df["Mercado"] == "Bolsa") & df["Codigo_Negociacao"].notna()]


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

    universo = universo_nao_financeiro()
    print(f"📋 Universo: {len(universo)} empresas não financeiras (ativas, bolsa, categoria A)")

    def _con_e_ind(ano, sigla, cd_contas, fonte="ITR"):
        con = ler_contas_todas_empresas(ano, sigla, "con", cd_contas, fonte)
        ind = ler_contas_todas_empresas(ano, sigla, "ind", cd_contas, fonte)
        return con, ind

    def _valor_com_fallback(con, ind, cd_conta):
        return _ultimo_valor_por_empresa(con, cd_conta).combine_first(_ultimo_valor_por_empresa(ind, cd_conta))

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


def resolver_tickers(tabela: pd.DataFrame, ano: int = None) -> pd.DataFrame:
    """
    Adiciona o ticker ON (.../3), PN (.../4) e Unit (.../11) de cada empresa,
    lidos do Formulário Cadastral. Uma empresa pode ter só ON, só PN, ON+PN,
    ou só Unit — o resto do pipeline lida com qualquer combinação.
    """
    ano = ano or date.today().year
    tickers_df = ler_tickers_todas_empresas(ano)
    tickers_df = tickers_df.copy()
    tickers_df["_CNPJ_NORM"] = tickers_df["CNPJ_Companhia"].apply(_normalizar_cnpj)

    def _primeiro_com_sufixo(codigos, sufixo):
        achados = [c for c in codigos if c.endswith(sufixo)]
        return achados[0] if achados else None

    mapa_on, mapa_pn, mapa_unit = {}, {}, {}
    for cnpj_norm, grupo in tickers_df.groupby("_CNPJ_NORM"):
        codigos = grupo["Codigo_Negociacao"].dropna().unique().tolist()
        mapa_on[cnpj_norm] = _primeiro_com_sufixo(codigos, "3")
        mapa_pn[cnpj_norm] = _primeiro_com_sufixo(codigos, "4")
        mapa_unit[cnpj_norm] = _primeiro_com_sufixo(codigos, "11")

    tabela = tabela.copy()
    cnpj_norm = tabela["CNPJ_CIA"].apply(_normalizar_cnpj)
    tabela["ticker_on"] = cnpj_norm.map(mapa_on)
    tabela["ticker_pn"] = cnpj_norm.map(mapa_pn)
    tabela["ticker_unit"] = cnpj_norm.map(mapa_unit)
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
            limite = divs.index.max() - pd.Timedelta(days=365)
            dividendos_12m = float(divs[divs.index >= limite].sum())

        return {
            "preco": preco, "acoes_em_circulacao": acoes_em_circulacao,
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

    for i, row in enumerate(tabela.itertuples(), start=1):
        if i % 25 == 0 or i == n:
            print(f"   📈 {i}/{n} empresas consultadas no yfinance...")

        cap_empresa = 0.0
        preco_ref = None
        div_total = 0.0
        vol_total = 0.0
        algum_dado = False

        for ticker in [row.ticker_on, row.ticker_pn]:
            if not ticker or pd.isna(ticker):
                continue
            if ticker not in cache_ticker:
                cache_ticker[ticker] = _dados_mercado_ticker(ticker)
                time.sleep(pausa)
            dados = cache_ticker[ticker]
            if not dados:
                continue
            algum_dado = True
            cap_empresa += dados["preco"] * dados["acoes_em_circulacao"]
            div_total += dados["dividendos_12m"]
            vol_total += dados["volume_medio_30d"]
            preco_ref = dados["preco"]  # referência de preço: a última classe válida encontrada

        # Sem ON nem PN cotados — tenta a Unit como aproximação
        if not algum_dado and row.ticker_unit and pd.notna(row.ticker_unit):
            if row.ticker_unit not in cache_ticker:
                cache_ticker[row.ticker_unit] = _dados_mercado_ticker(row.ticker_unit)
                time.sleep(pausa)
            dados = cache_ticker[row.ticker_unit]
            if dados:
                cap_empresa = dados["preco"] * dados["acoes_em_circulacao"]
                preco_ref = dados["preco"]
                div_total = dados["dividendos_12m"]
                vol_total = dados["volume_medio_30d"]

        market_cap.append(cap_empresa if cap_empresa else None)
        preco_referencia.append(preco_ref)
        dividendos_12m.append(div_total if preco_ref else None)
        volume_medio.append(vol_total if preco_ref else None)

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

    return tabela


def montar_screening(ano_fiscal: int = None, pausa_yfinance: float = 0.3) -> pd.DataFrame:
    """Orquestra o pipeline inteiro: fundamentos (CVM) → tickers (FCA) → mercado (yfinance) → indicadores."""
    tabela = coletar_fundamentos(ano_fiscal)
    tabela = resolver_tickers(tabela)
    print(f"📈 Buscando preço/dividendos/volume no yfinance para {len(tabela)} empresas...")
    tabela = buscar_dados_mercado(tabela, pausa=pausa_yfinance)
    tabela = calcular_indicadores(tabela)
    return tabela
