"""
Liquidez mensal e valor de mercado anual das ações da B3
(consulta avulsa, fora do pipeline da R.V. Mapp).

Liquidez — fonte: Séries Históricas da B3 (arquivos COTAHIST anuais).
  Volume financeiro médio diário do mês =
  volume financeiro negociado no mês / número de pregões do mês.

Valor de mercado em dezembro de cada ano:
  soma, por classe de ação (ON, PN, PNA, PNB...), de
  preço de fechamento no último pregão do ano (COTAHIST, sem ajuste) ×
  quantidade de ações do capital integralizado em 31/12 (CVM, Formulário de
  Referência, histórico do capital social pela data de aprovação).
  Classe sem negócio no ano usa o preço da classe mais negociada da empresa.

Filtros:
  - mercado à vista, lote padrão (TPMERC 010); fracionário fica de fora
  - só ações e units (classe do ISIN: ACN, CDA, UNT); ficam de fora
    FIIs, ETFs, BDRs, direitos e recibos

Uso:
    python liquidez_b3.py               # 2013 até o ano corrente
    python liquidez_b3.py 2013 2020     # intervalo de anos
    python liquidez_b3.py --rebaixar    # baixa de novo também os anos já guardados

Saída: data/processed/liquidez_mensal_b3.xlsx
"""
import io
import json
import re
import sys
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import requests

URL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{ano}.ZIP"
URL_FRE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/fre_cia_aberta_{ano}.zip"
URL_FCA = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FCA/DADOS/fca_cia_aberta_{ano}.zip"
PASTA_RAW = Path("data/raw")
PASTA_CACHE = PASTA_RAW / "cotahist"
SAIDA = Path("data/processed/liquidez_mensal_b3.xlsx")
CLASSES_ACAO = {"ACN", "CDA", "UNT"}

# classe da ação pelo ISIN (posições 7 a 11) -> classe usada no capital social
CLASSE_ISIN = {"ACNOR": "ON", "ACNPR": "PN", "ACNPA": "PNA", "ACNPB": "PNB",
               "ACNPC": "PNC", "ACNPD": "PND", "ACNPE": "PNE", "ACNPF": "PNF"}

# Raízes de ticker de empresas que saíram da bolsa ou trocaram de nome antes de
# 2018 (o FCA só traz ticker a partir de 2018). Conferidas no cadastro da CVM.
RAIZ_CNPJ_MANUAL = {
    "KROT": "02800026000140",  # Kroton -> Cogna
    "BRPR": "06977751000149",  # BR Properties
    "CTIP": "09358105000191",  # Cetip
    "SMLE": "15912764000120",  # Smiles S.A.
    "TBLE": "02474103000119",  # Tractebel -> Engie Brasil
    "CRUZ": "33009911000139",  # Souza Cruz
    "ALLL": "02387241000160",  # ALL -> Rumo S.A.
    "GETI": "02998609000127",  # AES Tietê
    "RUMO": "71550388000142",  # Rumo Logística (até 2015)
    "ABRE": "02541982000154",  # Abril Educação -> Somos
    "BRIN": "11721921000160",  # BR Insurance -> Alper
    "IMCH": "08936792000112",  # IMC Holdings
    "GETT": "10440482000154",  # Getnet
    "VAGR": "05799312000120",  # V-Agro -> Terra Santa Agro
    "HRTP": "10629105000168",  # HRT -> PetroRio -> PRIO
    "LLXL": "08741499000108",  # LLX -> Prumo
    "BEMA": "82373077000171",  # Bematech
    "DAYC": "62232889000190",  # Daycoval
    "AUTM": "59104513000195",  # Autometal
    "TEMP": "06977739000134",  # Tempo Participações
    "TERI": "11566501000156",  # Tereos Internacional
    "BPNM": "59285411000113",  # Panamericano -> Banco Pan
    "ADHM": "10345009000198",  # Advanced Digital Health
    "PRVI": "76500180000132",  # Providência
    "SGAS": "33228024000151",  # WLM
    "CMGR": "03467321000199",  # Cemat -> Energisa MT
    "BMTO": "61084984000120",  # Brasmotor
    "RJCP": "08281683000104",  # RJCP
    "IMBI": "84208123000102",  # Docas de Imbituba
    "MTIG": "80227184000166",  # Metalgráfica Iguaçu
    "TIBR": "15115504000124",  # Millennium -> Tronox Pigmentos
    "AMBV": "02808708000107",  # Cia de Bebidas das Américas (antes da Ambev S.A.)
    "MPXE": "04423567000121",  # MPX -> Eneva
    "NETC": "00108786000165",  # Net Serviços
    "EBTP": "02558124000112",  # Embratel Participações
    "TNCP": "02558154000129",  # Tele Norte Celular
    "AMIL": "36461242000120",  # Amil
    "ANDG": "03601314000138",  # AG Concessões
    "AFLU": "07620094000140",  # Afluente Geração
    "CBMA": "61080313000191",  # Cobrasma
    "CCHI": "52736840000110",  # Chiarelli
    "CIQU": "78588415000115",  # Cacique Café
    "CLAN": "24956666000186",  # Clarion
    "DOCA": "33433665000148",  # Docas Investimentos
    "GTDP": "00649881000176",  # GTD Participações
    "RDTR": "12126500000153",  # Redentor Energia
    "RSIP": "94789468000150",  # Rasip Agro
    "SCLO": "82981929000103",  # Schlosser
    "SGEN": "33161340000153",  # Sergen
    "SULT": "89723993000133",  # Sultepa
    "VINE": "07332190000193",  # Vicunha Têxtil
    "BVMF": "09346601000125",  # BM&FBovespa -> B3
}
PRIORIDADE_CAPITAL = {"Capital Integralizado": 0, "Capital Subscrito": 0.1, "Capital Emitido": 0.2}
VALOR_MAXIMO_PLAUSIVEL = 1e12  # nenhuma empresa da B3 chegou a R$ 1 trilhão


def _baixar_arquivo(url, arq, rebaixar=False):
    if arq.exists() and not rebaixar:
        return arq
    arq.parent.mkdir(parents=True, exist_ok=True)
    print(f"  baixando {arq.name}...", flush=True)
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    zipfile.ZipFile(io.BytesIO(r.content))  # confere se veio um zip válido
    arq.write_bytes(r.content)
    return arq


def baixar(ano, rebaixar=False):
    # o ano corrente sempre é baixado de novo, porque o arquivo cresce a cada pregão
    rebaixar = rebaixar or ano >= date.today().year
    return _baixar_arquivo(URL.format(ano=ano), PASTA_CACHE / f"COTAHIST_A{ano}.ZIP", rebaixar)


def ler(arq):
    """Lê o layout de largura fixa e devolve as linhas de ações do mercado à vista."""
    linhas = []
    pregoes = set()
    with zipfile.ZipFile(arq) as z, z.open(z.namelist()[0]) as f:
        for raw in f:
            l = raw.decode("latin-1")
            if l[:2] != "01":
                continue
            data = l[2:10]
            pregoes.add(data)
            if l[24:27] != "010" or l[236:239] not in CLASSES_ACAO:
                continue
            linhas.append((
                data,
                l[12:24].strip(),                          # ticker
                l[27:39].strip(),                          # nome resumido
                l[230:242],                                # ISIN
                int(l[147:152]),                           # número de negócios
                int(l[170:188]) / 100,                     # volume financeiro (2 casas implícitas)
                int(l[108:121]) / 100 / int(l[210:217]),   # fechamento por ação (÷ fator de cotação)
            ))
    df = pd.DataFrame(linhas, columns=["data", "ticker", "empresa", "isin", "negocios", "volume", "preco"])
    df["data"] = pd.to_datetime(df["data"], format="%Y%m%d")
    pregoes = pd.to_datetime(pd.Series(sorted(pregoes)), format="%Y%m%d")
    return df, pregoes


def _so_digitos(cnpj):
    return re.sub(r"\D", "", str(cnpj))


def _ler_csv_zip(arq, nome):
    with zipfile.ZipFile(arq) as z:
        if nome not in z.namelist():
            return pd.DataFrame()
        return pd.read_csv(z.open(nome), sep=";", encoding="latin1", dtype=str)


def mapa_ticker_cnpj(anos, rebaixar=False):
    """Ticker -> CNPJ pelo FCA da CVM (2018 em diante), e raiz do ticker -> CNPJ
    pela lista de empresas da B3 e pela lista manual das empresas antigas."""
    por_ticker = {}
    for ano in anos:
        if ano < 2018:
            continue
        arq = _baixar_arquivo(URL_FCA.format(ano=ano), PASTA_RAW / "fca" / f"fca_cia_aberta_{ano}.zip",
                              rebaixar or ano >= date.today().year)
        vm = _ler_csv_zip(arq, f"fca_cia_aberta_valor_mobiliario_{ano}.csv").dropna(subset=["Codigo_Negociacao"])
        for tk, cnpj in zip(vm["Codigo_Negociacao"], vm["CNPJ_Companhia"]):
            por_ticker[tk.strip()] = _so_digitos(cnpj)  # anos mais novos sobrescrevem

    por_raiz = {}
    for tk, cnpj in por_ticker.items():
        por_raiz.setdefault(tk[:4], cnpj)
    lista_b3 = PASTA_RAW / "b3_empresas_listadas.json"
    if lista_b3.exists():
        for emp in json.loads(lista_b3.read_text(encoding="utf-8")):
            por_raiz.setdefault(emp["issuingCompany"].strip(), _so_digitos(emp["cnpj"]))
    por_raiz.update(RAIZ_CNPJ_MANUAL)
    return por_ticker, por_raiz


def historico_capital(anos, rebaixar=False):
    """Quantidade de ações do capital integralizado, por empresa, classe e data de
    aprovação, juntando os Formulários de Referência de todos os anos."""
    partes = []
    for ano in anos:
        arq = _baixar_arquivo(URL_FRE.format(ano=ano), PASTA_RAW / "fre" / f"fre_cia_aberta_{ano}.zip",
                              rebaixar or ano >= date.today().year)
        cap = _ler_csv_zip(arq, f"fre_cia_aberta_capital_social_{ano}.csv")
        cls = _ler_csv_zip(arq, f"fre_cia_aberta_capital_social_classe_acao_{ano}.csv")
        # integralizado; se a empresa não informar, subscrito ou emitido
        cap = cap[cap["Tipo_Capital"].isin(PRIORIDADE_CAPITAL)].copy()
        cap["Versao"] = cap["Versao"].astype(int)
        cap["cnpj"] = cap["CNPJ_Companhia"].map(_so_digitos)
        # só a última versão entregue de cada formulário
        cap = cap[cap["Versao"] == cap.groupby("cnpj")["Versao"].transform("max")]

        for _, r in cap.iterrows():
            qtd = {"ON": float(r["Quantidade_Acoes_Ordinarias"] or 0),
                   "PN": float(r["Quantidade_Acoes_Preferenciais"] or 0)}
            classes = cls[cls["ID_Capital_Social"] == r["ID_Capital_Social"]]
            for tipo, q in zip(classes["Tipo_Classe_Acao_Preferencial"], classes["Quantidade_Acoes"]):
                m = re.match(r"Preferencial Classe ([A-F])$", str(tipo))
                if m and float(q or 0) > 0:
                    qtd["PN" + m.group(1)] = float(q)
            if any(k.startswith("PN") and len(k) == 3 for k in qtd):
                qtd["PN"] = 0.0  # preferenciais já separadas por classe
            for classe, q in qtd.items():
                if q > 0:
                    partes.append((r["cnpj"], r["Data_Autorizacao_Aprovacao"], ano,
                                   PRIORIDADE_CAPITAL[r["Tipo_Capital"]], classe, q))

        # desdobramentos, grupamentos e bonificações trazem a quantidade antes e
        # depois do evento: cobrem anos que o capital social do formulário já não mostra
        des = _ler_csv_zip(arq, f"fre_cia_aberta_capital_social_desdobramento_{ano}.csv")
        if des.empty:
            continue
        des["Versao"] = des["Versao"].astype(int)
        des["cnpj"] = des["CNPJ_Companhia"].map(_so_digitos)
        des = des[des["Versao"] == des.groupby("cnpj")["Versao"].transform("max")]
        for _, r in des.iterrows():
            aprov = pd.to_datetime(r["Data_Aprovacao"], errors="coerce")
            if pd.isna(aprov):
                continue
            for quando, data in (("Antes", aprov - pd.Timedelta(days=1)), ("Depois", aprov)):
                for classe, campo in (("ON", "Ordinarias"), ("PN", "Preferenciais")):
                    q = float(r[f"Quantidade_Acoes_{campo}_{quando}_Aprovacao"] or 0)
                    if q > 0:
                        partes.append((r["cnpj"], data.date().isoformat(), ano, 1, classe, q))

    h = pd.DataFrame(partes, columns=["cnpj", "data_aprovacao", "ano_fre", "fonte", "classe", "acoes"])
    h["data_aprovacao"] = pd.to_datetime(h["data_aprovacao"], errors="coerce")
    h = h.dropna(subset=["data_aprovacao"])
    # mesma data: o capital social (com as classes) vale mais que o desdobramento,
    # e o formulário mais novo vale mais que o antigo
    chave = ["cnpj", "data_aprovacao"]
    h = h[h["fonte"] == h.groupby(chave)["fonte"].transform("min")]
    h = h[h["ano_fre"] == h.groupby(chave)["ano_fre"].transform("max")]
    return h.drop(columns=["ano_fre", "fonte"]).drop_duplicates(chave + ["classe"])


def ajustar_datas_eventos(capital, acoes):
    """Desdobramento e grupamento são aprovados numa data e passam a valer na bolsa
    depois. Quando a quantidade de ações muda de escala (mais de 25%), procura em
    até 180 dias após a aprovação o pregão em que o preço salta na proporção
    inversa, e usa essa data no lugar da aprovação."""
    total = capital.groupby(["cnpj", "data_aprovacao"])["acoes"].sum().reset_index()
    # preço diário da classe mais negociada de cada empresa (no dia, o ticker de
    # maior volume da classe, para atravessar trocas de código como VIIA3 -> BHIA3)
    vol = acoes.groupby(["cnpj", "classe"])["volume"].sum()
    principal = set(vol.loc[vol.groupby(level=0).idxmax()].index)
    acoes = acoes[[k in principal for k in zip(acoes["cnpj"], acoes["classe"])]]
    precos = (acoes.sort_values(["data", "volume"]).drop_duplicates(["cnpj", "data"], keep="last")
                   .groupby("cnpj")[["data", "preco"]])
    novas_datas = {}
    for cnpj, h in total.groupby("cnpj"):
        if cnpj not in precos.groups:
            continue
        p = precos.get_group(cnpj).drop_duplicates("data").set_index("data")["preco"]
        salto = p / p.shift(1)
        h = h.sort_values("data_aprovacao")
        for (_, ant), (_, novo) in zip(h.iloc[:-1].iterrows(), h.iloc[1:].iterrows()):
            fator = novo["acoes"] / ant["acoes"]
            if 0.8 <= fator <= 1.25:
                continue
            # mudança grande (grupamento/desdobramento de verdade) às vezes só chega
            # ao formulário bem depois: procura desde o registro anterior
            inicio = ant["data_aprovacao"] if not 0.4 <= fator <= 2.5 else novo["data_aprovacao"]
            janela = salto[(salto.index > inicio)
                           & (salto.index <= novo["data_aprovacao"] + pd.Timedelta(days=180))]
            bate = janela[(janela * fator > 0.6) & (janela * fator < 1.6)]
            if not bate.empty:
                novas_datas[(cnpj, novo["data_aprovacao"])] = bate.index[0] - pd.Timedelta(days=1)
    if novas_datas:
        chave = list(zip(capital["cnpj"], capital["data_aprovacao"]))
        capital = capital.copy()
        capital["data_aprovacao"] = [novas_datas.get(k, k[1]) for k in chave]
    return capital, len(novas_datas)


def valor_mercado(df, anos, rebaixar=False):
    """Valor de mercado em dezembro de cada ano completo, por empresa (CNPJ)."""
    por_ticker, por_raiz = mapa_ticker_cnpj(anos, rebaixar)
    capital = historico_capital(anos, rebaixar)

    acoes = df[df["isin"].str[6:11].isin(CLASSE_ISIN)].copy()
    acoes["classe"] = acoes["isin"].str[6:11].map(CLASSE_ISIN)
    acoes["cnpj"] = acoes["ticker"].map(por_ticker)
    sem = acoes["cnpj"].isna()
    acoes.loc[sem, "cnpj"] = acoes.loc[sem, "isin"].str[2:6].map(por_raiz)
    sem = acoes["cnpj"].isna()
    acoes.loc[sem, "cnpj"] = acoes.loc[sem, "ticker"].str[:4].map(por_raiz)
    acoes["ano"] = acoes["data"].dt.year
    capital, n_ajustes = ajustar_datas_eventos(capital, acoes.dropna(subset=["cnpj"]))
    print(f"  {n_ajustes} desdobramentos/grupamentos com data ajustada à da bolsa", flush=True)

    ano_corrente = date.today().year
    detalhe = []
    for ano in anos:
        if ano >= ano_corrente:
            continue  # dezembro ainda não aconteceu
        do_ano = acoes[acoes["ano"] == ano].dropna(subset=["cnpj"])
        fim = pd.Timestamp(ano, 12, 31)
        cap_ate = capital[capital["data_aprovacao"] <= fim]
        cap_ate = cap_ate[cap_ate["data_aprovacao"] == cap_ate.groupby("cnpj")["data_aprovacao"].transform("max")]

        for cnpj, negs in do_ano.groupby("cnpj"):
            # só empresas com negócio em dezembro (ainda listadas no fim do ano)
            if negs["data"].max().month != 12:
                continue
            qtd = cap_ate[cap_ate["cnpj"] == cnpj]
            if qtd.empty:
                detalhe.append({"ano": ano, "cnpj": cnpj, "obs": "sem quantidade de ações na CVM"})
                continue
            # último fechamento do ano de cada classe; se houver mais de um ticker na
            # classe (troca de código), vale o de negócio mais recente
            ult = negs.sort_values(["data", "volume"]).groupby("classe").last()
            vol = negs.groupby("classe")["volume"].sum()
            preco_ref = ult.loc[vol.idxmax()]
            for _, q in qtd.iterrows():
                classe = q["classe"]
                # PN genérica na CVM e PNA na bolsa (ou o contrário): mesma espécie
                mesma_especie = vol[[c for c in vol.index if c[:2] == classe[:2]]]
                if classe in ult.index:
                    p, obs = ult.loc[classe], ""
                elif not mesma_especie.empty:
                    p = ult.loc[mesma_especie.idxmax()]
                    obs = f"{classe} na CVM, preço de {p['ticker']}"
                else:
                    p, obs = preco_ref, f"{classe} sem negócio no ano: usado o preço de {preco_ref['ticker']}"
                detalhe.append({
                    "ano": ano, "cnpj": cnpj, "classe": classe, "acoes": q["acoes"],
                    "capital_aprovado_em": q["data_aprovacao"].date(),
                    "ticker_preco": p["ticker"], "data_preco": p["data"].date(), "preco": p["preco"],
                    "valor": q["acoes"] * p["preco"], "obs": obs,
                })

    det = pd.DataFrame(detalhe)
    nomes = (acoes.dropna(subset=["cnpj"]).sort_values("data").groupby("cnpj")
                  .agg(empresa=("empresa", "last"), tickers=("ticker", lambda s: ", ".join(sorted(set(s))))))
    total = det.dropna(subset=["valor"]).groupby(["cnpj", "ano"])["valor"].sum()
    # valor impossível (erro de escala na quantidade de ações informada) fica fora
    absurdo = total[total > VALOR_MAXIMO_PLAUSIVEL].index
    total = total.drop(absurdo)
    # salto de mais de 20 vezes de um ano para o outro: mantém, mas avisa
    variacao = total / total.groupby("cnpj").shift(1)
    saltos = variacao[(variacao > 20) | (variacao < 1 / 20)].index
    det["alerta"] = ""
    chave = pd.MultiIndex.from_frame(det[["cnpj", "ano"]])
    det.loc[chave.isin(saltos), "alerta"] = "variação de mais de 20x sobre o ano anterior: conferir"
    det.loc[chave.isin(absurdo), "alerta"] = "valor acima de R$ 1 tri: fora da tabela (quantidade de ações suspeita)"
    tabela = total.unstack("ano")
    tabela.columns = [f"dez/{a}" for a in tabela.columns]
    tabela = nomes.join(tabela, how="right")
    det = det.join(nomes["empresa"], on="cnpj")
    sem_cnpj = sorted(acoes.loc[acoes["cnpj"].isna(), "ticker"].unique())
    return tabela, det, sem_cnpj, por_ticker, por_raiz


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    rebaixar = "--rebaixar" in sys.argv
    ano_ini = int(args[0]) if args else 2013
    ano_fim = int(args[1]) if len(args) > 1 else date.today().year
    anos = list(range(ano_ini, ano_fim + 1))

    partes, todos_pregoes = [], []
    for ano in anos:
        print(f"{ano}:", flush=True)
        df, pregoes = ler(baixar(ano, rebaixar))
        print(f"  {len(df):,} linhas de ações, {len(pregoes)} pregões", flush=True)
        partes.append(df)
        todos_pregoes.append(pregoes)

    df = pd.concat(partes, ignore_index=True)
    pregoes = pd.concat(todos_pregoes)
    df["mes"] = df["data"].dt.to_period("M")
    pregoes_mes = pregoes.dt.to_period("M").value_counts().rename("pregoes_mes")

    base = (df.groupby(["ticker", "mes"])
              .agg(volume_total=("volume", "sum"),
                   negocios=("negocios", "sum"),
                   dias_com_negocio=("data", "nunique"))
              .reset_index()
              .join(pregoes_mes, on="mes"))
    base["volume_medio_diario"] = base["volume_total"] / base["pregoes_mes"]

    print("valor de mercado (CVM):", flush=True)
    vm, vm_detalhe, sem_cnpj, por_ticker, por_raiz = valor_mercado(df, anos, rebaixar)

    # nome e ISIN mais recentes de cada ticker, e a empresa (CNPJ) a que pertence
    ultimo = (df.sort_values("data").groupby("ticker").last()[["empresa", "isin"]])
    ultimo["cnpj"] = [por_ticker.get(tk) or por_raiz.get(isin[2:6]) or por_raiz.get(tk[:4])
                      for tk, isin in zip(ultimo.index, ultimo["isin"])]

    tabela = base.pivot(index="ticker", columns="mes", values="volume_medio_diario")
    tabela.columns = [str(c) for c in tabela.columns]
    tabela = ultimo.join(tabela, how="right")

    base["mes"] = base["mes"].astype(str)
    ultima_data = df["data"].max().date()

    notas = pd.DataFrame({"Notas": [
        "Fonte da liquidez e dos preços: B3, Séries Históricas (arquivos COTAHIST anuais).",
        "Volume médio diário = volume financeiro negociado no mês / número de pregões do mês (R$).",
        "Mês sem valor = ação sem negócio no mês (ou ainda não listada / já deslistada).",
        "Mercado à vista, lote padrão; o fracionário não está incluído.",
        "Só ações e units (ISIN classe ACN, CDA, UNT); sem FIIs, ETFs, BDRs, direitos e recibos.",
        "Ticker como negociado em cada mês: trocas de código aparecem como linhas separadas (o ISIN e o CNPJ ajudam a ligar).",
        f"Último pregão no arquivo: {ultima_data:%d/%m/%Y} (o último mês pode estar incompleto).",
        "",
        "Valor de mercado (R$) em dezembro = soma, por classe (ON, PN, PNA, PNB...), de fechamento no último pregão do ano × quantidade de ações.",
        "Quantidade de ações: capital integralizado na CVM (Formulário de Referência; subscrito ou emitido quando a empresa não informa o integralizado), mais desdobramentos, grupamentos e bonificações. Inclui ações em tesouraria.",
        "Data da quantidade: a da aprovação; em desdobramento/grupamento, a do pregão em que o preço saltou na mesma proporção (quando a bolsa passou a negociar a nova quantidade).",
        "Preço sem ajuste por proventos ou desdobramentos (é o preço do dia). Classe sem negócio no ano usa o preço da classe mais negociada (ver aba 'Valor de mercado detalhe').",
        "Units não entram na soma (são pacotes de ON e PN, que já estão contadas).",
        "Só empresas com negócio em dezembro do ano. O ano corrente não tem dezembro ainda.",
        f"Tickers sem empresa identificada na CVM (fora do valor de mercado): {', '.join(sem_cnpj) or 'nenhum'}.",
    ]})

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(SAIDA, engine="openpyxl") as xl:
        tabela.to_excel(xl, sheet_name="Volume medio diario")
        base.to_excel(xl, sheet_name="Base mensal", index=False)
        vm.to_excel(xl, sheet_name="Valor de mercado (dez)")
        vm_detalhe.to_excel(xl, sheet_name="Valor de mercado detalhe", index=False)
        notas.to_excel(xl, sheet_name="Notas", index=False)
    print(f"\nOK: {len(tabela)} tickers, {tabela.shape[1] - 3} meses; "
          f"valor de mercado de {len(vm)} empresas -> {SAIDA}")


if __name__ == "__main__":
    main()
