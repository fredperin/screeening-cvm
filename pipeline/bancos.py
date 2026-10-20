"""
Instituições financeiras: dados do IF.data do Banco Central (API oficial Olinda), por conglomerado
prudencial ou instituição independente (TipoInstituicao = 1), na estrutura da planilha de rating de
emissores bancários do usuário (abas INFO, DFS, CARTEIRA_RESUMO e CARTEIRA_TOTAL).

- Layout novo (Resolução CMN 4.966, desde o 1º tri de 2025): balanço, DRE, capital e carteiras completos.
- Histórico longo (desde 2015, layout antigo e novo): só as linhas que existem nos dois — ativo total,
  carteira de crédito, captações, patrimônio líquido, lucro líquido e índice de Basileia.
- Resultado: o IF.data informa o trimestre em março e setembro e o semestre em junho e dezembro; o
  2º e o 4º trimestres saem por diferença (junho − março; dezembro − setembro).
- Cada trimestre baixado fica guardado (data/raw/ifdata); só o trimestre mais recente é rebaixado
  (o BC revisa) e trimestres novos são buscados quando aparecem.

Saída: site/dados/bancos.json (lista) e site/dados/bancos/{id}.json (uma instituição).
Uso: py -m pipeline.bancos
"""

import json
import os
import re
import time
from datetime import date, datetime, timedelta, timezone

import requests

from config.config import RAW_DIR
from pipeline import DIR_DADOS_SITE

API = "https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata/"
DIR_CACHE = RAW_DIR / "ifdata"
DIR_BANCOS = DIR_DADOS_SITE / "bancos"
FUSO_BR = timezone(timedelta(hours=-3))
INICIO_LAYOUT_NOVO = 202503
INICIO_HISTORICO = 201503
RELATORIOS_NOVOS = {"resumo": "1", "ativo": "2", "passivo": "3", "dre": "4", "capital": "5", "indexador": "7", "regiao": "9",
                    "clientes": "10", "pf": "11", "pj": "13", "porte": "14", "carteiras": "16"}

TIPOS = {"B1": "Banco comercial / múltiplo com carteira comercial", "B2": "Banco múltiplo sem carteira comercial / investimento",
         "B4": "Banco de desenvolvimento", "N1": "Não bancário de crédito", "N2": "Não bancário do mercado de capitais",
         "N4": "Instituição de pagamento", "B3S": "Cooperativa de crédito singular", "B3C": "Central e confederação de cooperativas"}
CONTROLE = {1: "Público", 2: "Privado nacional", 3: "Privado com controle estrangeiro"}

# Bancos listados na B3 (conglomerado prudencial no IF.data -> ticker), para o perfil com dados da CVM e da B3
LISTADOS = {"C0080099": "ITUB4", "C0080075": "BBDC4", "C0080329": "BBAS3", "C0080185": "SANB11", "C0080336": "BPAC11",
            "C0080312": "ABCB4", "C0080154": "BRSR6", "C0080178": "BMGB4", "C0080374": "PINE4", "C0080123": "BMEB4",
            "C0080147": "BEES3", "C0080288": "BSLI4", "C0081586": "BPAR3", "C0081634": "BGIP4", "C0081249": "BAZA3",
            "C0081593": "BNBR3"}

# ---- estrutura das tabelas (mesma ordem e nomes da aba DFS da planilha); código = letra do IF.data ----
LAYOUT_ATIVO = [("a", "Disponibilidades", 0), ("b", "Aplicações Interfinanceiras de Liquidez", 0), ("c", "Títulos e Valores Mobiliários", 0),
                ("d", "Instrumentos Derivativos", 0), ("e", "Operações de Crédito", 0), ("e1", "Valor Contábil Bruto", 1),
                ("e2", "Perda Esperada", 1), ("e3", "Hedge de Valor Justo", 1), ("e4", "Ajuste a Valor Justo", 1),
                ("f", "Operações de Arrendamento Financeiro", 0), ("f1", "Valor Contábil Bruto", 1), ("f2", "Perda Esperada", 1),
                ("f3", "Hedge de Valor Justo", 1), ("g", "Outras Operações com Características de Concessão de Crédito", 0),
                ("g1", "Valor Contábil Bruto", 1), ("g2", "Perda Esperada", 1), ("g3", "Hedge de Valor Justo", 1),
                ("g4", "Ajuste a Valor Justo", 1), ("h", "Valores a Receber de Transações de Pagamento", 0),
                ("h1", "Valor Contábil Bruto", 1), ("h2", "Perda Esperada", 1), ("i", "Outros Ativos Realizáveis", 0),
                ("j", "Ativo Permanente", 0), ("k", "ATIVO TOTAL", -1)]
LAYOUT_PASSIVO = [("e", "Funding Total", 0), ("a", "Depósitos", 1), ("a1", "Depósitos à Vista", 2), ("a2", "Depósitos de Poupança", 2),
                  ("a3", "Depósitos Interfinanceiros", 2), ("a4", "Depósitos a Prazo", 2), ("a5", "Conta de Pagamento Pré-Paga", 2),
                  ("a6", "Depósitos Outros", 2), ("b", "Obrigações por Operações Compromissadas", 1), ("c", "Outros Instrumentos de Dívida", 1),
                  ("c1", "Letras de Crédito Imobiliário", 2), ("c2", "Letras de Crédito do Agronegócio", 2), ("c3", "Letras Financeiras", 2),
                  ("c4", "Obrigações por Títulos e Valores Mobiliários no Exterior", 2), ("c5", "Demais instrumentos de dívida", 2),
                  ("d", "Obrigações por Empréstimos e Repasses", 1), ("f", "Instrumentos Derivativos", 0), ("g", "Outras Obrigações", 0),
                  ("h", "Instrumentos de Dívida Elegíveis a Capital", 0), ("i", "Passivo Exigível", -2), ("j", "Patrimônio Líquido", 0),
                  ("k", "Passivo Total", -1)]
# DRE: "=..." são linhas calculadas a partir das letras do IF.data
LAYOUT_DRE = [("=receitas", "Receitas da Intermediação Financeira", -2), ("a", "Rendas de Aplicações Interfinanceiras de Liquidez", 1),
              ("a1", "Receita de Juros com Aplicações Interfinanceiras", 2), ("a2", "Ajuste de Variação Cambial de Aplicações", 2),
              ("a3", "Ajuste a Valor Justo e Hedge de Aplicações", 2), ("b", "Rendas de Títulos e Valores Mobiliários", 1),
              ("b1", "Receita de Juros com TVM", 2), ("b2", "Ajuste de Variação Cambial de TVM", 2), ("b3", "Ajuste a Valor Justo e Hedge de TVM", 2),
              ("b4", "Outros Resultados de TVM", 2), ("c", "Rendas de Operações de Crédito", 1), ("c1", "Receita de Juros com Operações de Crédito", 2),
              ("c2", "Ajuste de Variação Cambial de Operações de Crédito", 2), ("c3", "Ajuste a Valor Justo e Hedge de Operações de Crédito", 2),
              ("c4", "Outros Resultados de Operações de Crédito", 2), ("d", "Rendas de Arrendamento Financeiro", 1),
              ("e", "Rendas de Outras Operações com Características de Concessão de Crédito", 1), ("j", "Outros Resultados de Intermediação Financeira", 1),
              ("i", "Resultado com Derivativos", 1), ("g", "Despesas de Captações", 1), ("g1", "Despesa de Juros com Captações", 2),
              ("g2", "Ajuste de Variação Cambial de Captações", 2), ("g3", "Ajuste de Hedge de Valor Justo de Captações", 2),
              ("g4", "Outros Resultados de Captações", 2), ("h", "Despesas de Instrumentos de Dívida Elegíveis a Capital", 1),
              ("=antes_pdd", "RESULTADO DA INTERMEDIAÇÃO", -2), ("f", "Perda Esperada (PDD)", 0),
              ("f1", "Resultado com Perda Esperada de Aplicações Interfinanceiras", 1), ("f2", "Resultado com Perda Esperada de TVM", 1),
              ("f3", "Resultado com Perda Esperada de Operações de Crédito", 1), ("f4", "Resultado com Perda Esperada de Arrendamento", 1),
              ("f5", "Resultado com Perda Esperada de Outras Operações de Crédito", 1), ("f6", "Resultado com Perda Esperada de Outros Ativos", 1),
              ("k", "RESULTADO LÍQUIDO DA INTERMEDIAÇÃO", -2), ("l", "Resultado com Transações de Pagamento", 0),
              ("l1", "Resultado com Serviços por Transações de Pagamento", 1), ("l2", "Resultados de Perda Esperada com Transações de Pagamento", 1),
              ("l3", "Outros Resultados com Transações de Pagamento", 1), ("m", "Rendas de Tarifas Bancárias", 0),
              ("n", "Outras Rendas de Prestação de Serviços", 0), ("o", "Despesas de Pessoal", 0), ("p", "Despesas Administrativas", 0),
              ("r", "Despesas Tributárias", 0), ("t", "Outras Receitas", 0), ("u", "Outras Despesas", 0), ("s", "Resultado de Participações", 0),
              ("q", "Resultado com Perdas Esperadas de Outras Operações", 0), ("w", "RESULTADO ANTES DA TRIBUTAÇÃO E PARTICIPAÇÕES", -2),
              ("x", "Imposto de Renda e Contribuição Social", 0), ("=antes_part", "RESULTADO ANTES DE PARTICIPAÇÕES", -2),
              ("y", "Participações no Lucro", 0), ("z", "LUCRO LÍQUIDO", -1), ("aa", "Juros Sobre Capital Próprio de Cooperativas", 0)]
LAYOUT_CAPITAL = [("e", "Patrimônio de Referência", 0), ("c", "Capital Nível I", 0), ("a", "Capital Principal", 1), ("b", "Capital Complementar", 1),
                  ("d", "Capital Nível II", 0), ("j", "Ativos Ponderados pelo Risco (RWA)", 0), ("f", "RWA para Risco de Crédito", 1),
                  ("g", "RWA para Risco de Mercado", 1), ("h", "RWA para Risco Operacional", 1), ("i", "RWAsp", 1), ("k", "Exposição Total", 0),
                  ("l", "Índice de Capital Principal", 0), ("m", "Índice de Capital Nível I", 0), ("n", "Índice de Basileia", 0),
                  ("=adicional", "Adicional de Capital Principal", 0), ("o", "Razão de Alavancagem", 0)]
INDICES_CAPITAL = {"l", "m", "n", "o"}  # em fração (0,16 = 16%)
PRAZOS = ["Vencido a Partir de 15 Dias", "A Vencer em até 90 Dias", "A Vencer Entre 91 a 360 Dias", "A Vencer Entre 361 a 1080 Dias",
          "A Vencer Entre 1081 a 1800 Dias", "A Vencer Entre 1801 a 5400 Dias", "A Vencer Acima de 5400 Dias"]


def _get(url, tentativas=4):
    for i in range(tentativas):
        try:
            r = requests.get(url, timeout=300)
            r.raise_for_status()
            return r.json()["value"]
        except (requests.RequestException, ValueError, KeyError):
            if i == tentativas - 1:
                raise
            time.sleep(5 * (i + 1))


def _valores(anomes, rel):
    url = (API + "IfDataValores(AnoMes=@AnoMes,TipoInstituicao=@TipoInstituicao,Relatorio=@Relatorio)"
           f"?@AnoMes={anomes}&@TipoInstituicao=1&@Relatorio='{rel}'&$format=json&$select=CodInst,Grupo,NomeColuna,Saldo")
    return _get(url)


def _trimestres(inicio, fim):
    a, m = divmod(inicio, 100)
    saida = []
    while a * 100 + m <= fim:
        saida.append(a * 100 + m)
        m += 3
        if m > 12:
            a, m = a + 1, m - 12
    return saida


def ultimo_trimestre():
    hoje = date.today()
    for am in reversed(_trimestres(INICIO_LAYOUT_NOVO, hoje.year * 100 + hoje.month)):
        url = (API + "IfDataValores(AnoMes=@AnoMes,TipoInstituicao=@TipoInstituicao,Relatorio=@Relatorio)"
               f"?@AnoMes={am}&@TipoInstituicao=1&@Relatorio='1'&$format=json&$top=1")
        if _get(url):
            return am
    raise RuntimeError("IF.data sem trimestre disponível")


def relatorio(anomes, rel, ultimo):
    """Linhas do relatório (cache em disco; o trimestre mais recente é rebaixado se o cache tiver mais de 6 dias)."""
    import gzip
    DIR_CACHE.mkdir(parents=True, exist_ok=True)
    arq = DIR_CACHE / f"r{rel}_{anomes}.json.gz"  # comprimido: os relatórios de carteira passam de 30 MB
    antigo = DIR_CACHE / f"r{rel}_{anomes}.json"
    if antigo.exists() and not arq.exists():
        arq.write_bytes(gzip.compress(antigo.read_bytes()))
        os.utime(arq, (antigo.stat().st_atime, antigo.stat().st_mtime))
        antigo.unlink()
    velho = arq.exists() and anomes == ultimo and (time.time() - arq.stat().st_mtime) > 6 * 86400
    if arq.exists() and not velho:
        return json.loads(gzip.decompress(arq.read_bytes()).decode("utf-8"))
    linhas = [{"CodInst": l["CodInst"], "Grupo": l.get("Grupo"), "NomeColuna": l["NomeColuna"], "Saldo": l.get("Saldo")}
              for l in _valores(anomes, rel)]
    arq.write_bytes(gzip.compress(json.dumps(linhas, ensure_ascii=False, separators=(",", ":")).encode("utf-8")))
    return linhas


def _codigo(nome):
    m = re.search(r"\(([a-z]{1,2}\d?)\)", nome or "")
    return m.group(1) if m else None


def _primeira_linha(nome):
    return re.sub(r"\s*\([a-z]{1,2}\d?\).*$", "", (nome or "").split("\n")[0]).strip()


def _por_instituicao(linhas, chave):
    saida = {}
    for l in linhas:
        k = chave(l)
        if k is None or l.get("Saldo") is None:
            continue
        saida.setdefault(l["CodInst"], {})[k] = float(l["Saldo"])
    return saida


def _cadastro(anomes):
    url = API + f"IfDataCadastro(AnoMes=@AnoMes)?@AnoMes={anomes}&$format=json"
    return {c["CodInst"]: c for c in _get(url)}


def _trimestral(valores_por_data, datas):
    """Valores acumulados no semestre (jun/dez) -> trimestre."""
    saida = []
    for i, am in enumerate(datas):
        v = valores_por_data.get(am)
        if v is None:
            saida.append(None)
            continue
        if am % 100 in (6, 12):
            anterior = valores_por_data.get(am - 3)
            saida.append(None if anterior is None else v - anterior)
        else:
            saida.append(v)
    return saida


def _iso(am):
    a, m = divmod(am, 100)
    return (date(a + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)).isoformat()


# Bancos listados que não aparecem no IF.data: demonstrações da CVM (ITR/DFP), com aviso no site
SO_CVM = {"BRBI11": ("10739356000103", "BR PARTNERS S.A.", "Banco de investimento — dados da CVM (fora do IF.data)")}


def gerar_cvm(ticker, cnpj, nome, tipo):
    """Balanço e DRE trimestral de um banco direto dos ZIPs ITR/DFP da CVM (contas até o 3º nível)."""
    import pandas as pd
    from pipeline.cvm_lote import _caminho_zip, _ler_zip_filtrado

    partes = []
    for fonte in ("ITR", "DFP"):
        for ano in range(date.today().year - 5, date.today().year + 1):
            z = _caminho_zip(ano, fonte)
            if z.exists():
                partes.append(_ler_zip_filtrado(z, ano, fonte, {cnpj}))
    df = pd.concat([p for p in partes if not p.empty], ignore_index=True)
    df = df[df["ORDEM_EXERC"].str.upper().str.startswith("ÚLTIMO")]
    tipo_df = "con" if (df["TIPO"] == "con").any() else "ind"
    df = df[df["TIPO"] == tipo_df].copy()
    df["VERSAO"] = pd.to_numeric(df["VERSAO"])
    df = df.sort_values("VERSAO").drop_duplicates(["FONTE", "DT_REFER", "SIGLA", "CD_CONTA", "DT_INI_EXERC", "DT_FIM_EXERC"], keep="last")
    df["VALOR"] = df["VL_CONTA"] * df["ESCALA_MOEDA"].str.upper().map({"MIL": 1000.0}).fillna(1.0)
    df = df[df["CD_CONTA"].str.count(r"\.") <= 2]
    trimestres = sorted(df.loc[df["SIGLA"] == "BPA", "DT_FIM_EXERC"].unique())

    def balanco(sigla):
        b = df[(df["SIGLA"] == sigla) & (df["DT_FIM_EXERC"].isin(trimestres))]
        contas = b.sort_values("DT_FIM_EXERC").drop_duplicates("CD_CONTA", keep="last").sort_values("CD_CONTA")
        piv = b.pivot_table(index="CD_CONTA", columns="DT_FIM_EXERC", values="VALOR", aggfunc="last")
        return [{"k": c, "r": d, "n": -1 if "." not in c else c.count(".") - 1,
                 "v": [None if pd.isna(piv.loc[c].get(t)) else round(float(piv.loc[c].get(t)), 2) for t in trimestres]}
                for c, d in zip(contas["CD_CONTA"], contas["DS_CONTA"])]

    dre = df[df["SIGLA"] == "DRE"].copy()
    dre["DIAS"] = (pd.to_datetime(dre["DT_FIM_EXERC"]) - pd.to_datetime(dre["DT_INI_EXERC"])).dt.days
    trimestrais = dre[(dre["FONTE"] == "ITR") & (dre["DIAS"] < 100)]
    anuais = dre[(dre["FONTE"] == "DFP") & (dre["DIAS"] > 300)]
    contas = dre.sort_values("DT_FIM_EXERC").drop_duplicates("CD_CONTA", keep="last").sort_values("CD_CONTA")
    linhas_dre = []
    for c, d in zip(contas["CD_CONTA"], contas["DS_CONTA"]):
        valores = []
        for t in trimestres:
            q = trimestrais[(trimestrais["CD_CONTA"] == c) & (trimestrais["DT_FIM_EXERC"] == t)]["VALOR"]
            if len(q):
                valores.append(round(float(q.iloc[0]), 2))
            elif t.endswith("12-31"):  # 4º tri = ano (DFP) − 9 meses
                a = anuais[(anuais["CD_CONTA"] == c) & (anuais["DT_FIM_EXERC"] == t)]["VALOR"]
                tres = [trimestrais[(trimestrais["CD_CONTA"] == c) & (trimestrais["DT_FIM_EXERC"] == f"{t[:4]}-{m}")]["VALOR"]
                        for m in ("03-31", "06-30", "09-30")]
                valores.append(round(float(a.iloc[0]) - sum(float(x.iloc[0]) for x in tres), 2) if len(a) and all(len(x) for x in tres) else None)
            else:
                valores.append(None)
        linhas_dre.append({"k": c, "r": d, "n": -1 if "." not in c else c.count(".") - 1, "v": valores})
    def sem_zeradas(linhas):  # o modelo da CVM traz muitas linhas que não se aplicam a banco (sempre zero)
        return [l for l in linhas if any(v not in (None, 0) for v in l["v"]) or "." not in l["k"]]

    ativo, passivo, linhas_dre = sem_zeradas(balanco("BPA")), sem_zeradas(balanco("BPP")), sem_zeradas(linhas_dre)

    def achar(linhas, *termos, nivel=None):
        for l in linhas:
            if any(t.lower() in l["r"].lower() for t in termos) and (nivel is None or l["k"].count(".") == nivel):
                return l["v"]
        return [None] * len(trimestres)

    pl = achar(passivo, "Patrimônio Líquido", nivel=1)
    lucro = achar(linhas_dre, "Lucro ou Prejuízo Líquido", "Lucro/Prejuízo", "Lucro Líquido", nivel=1)
    total_ativo = next((l["v"] for l in ativo if l["k"] == "1"), [None] * len(trimestres))
    id_ = ticker.lower()
    detalhe = {"id": id_, "cod": None, "nome": nome, "segmento": None, "tipo_cod": "B2", "tipo": tipo, "controle": "Privado nacional",
               "uf": "SP", "municipio": "São Paulo", "ticker": ticker, "fonte": "CVM", "trimestres": list(trimestres),
               "resumo": {"Ativo Total": total_ativo, "Patrimônio Líquido": pl, "Lucro Líquido": lucro},
               "ativo": ativo, "passivo": passivo, "dre": linhas_dre, "capital": [], "carteiras": {}, "clientes": {},
               "historico": {"datas": list(trimestres), "ativo": total_ativo, "pl": pl, "lucro_tri": lucro}}
    (DIR_BANCOS / f"{id_}.json").write_text(json.dumps(detalhe, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ult4 = [x for x in lucro[-4:] if x is not None]
    lucro_12m = sum(ult4) if len(ult4) == 4 else None
    return {"id": id_, "cod": None, "nome": nome, "segmento": None, "tipo_cod": "B2", "controle": "Privado nacional", "uf": "SP",
            "ticker": ticker, "fonte": "CVM", "ativo": total_ativo[-1], "carteira": None, "pl": pl[-1], "lucro_12m": lucro_12m,
            "roe": lucro_12m / pl[-1] if lucro_12m is not None and pl[-1] else None, "basileia": None, "inadimplencia": None}


def gerar():
    ultimo = ultimo_trimestre()
    novos = _trimestres(INICIO_LAYOUT_NOVO, ultimo)
    historico = _trimestres(INICIO_HISTORICO, ultimo)
    cadastro = _cadastro(ultimo)

    # ---- layout novo: um dicionário por relatório -> {AnoMes: {CodInst: {chave: valor}}} ----
    def chave_codigo(l):
        return _codigo(l["NomeColuna"])

    def chave_nome(l):
        return _primeira_linha(l["NomeColuna"])

    def chave_grupo(l):
        return f"{l.get('Grupo') or ''}|{_primeira_linha(l['NomeColuna'])}"

    chaves = {"resumo": chave_nome, "ativo": chave_codigo, "passivo": chave_codigo, "dre": chave_codigo, "capital": chave_codigo,
              "indexador": chave_nome, "regiao": chave_nome, "clientes": chave_nome, "pf": chave_grupo, "pj": chave_grupo,
              "porte": chave_nome, "carteiras": chave_nome}
    dados = {nome: {am: _por_instituicao(relatorio(am, rel, ultimo), chaves[nome]) for am in novos}
             for nome, rel in RELATORIOS_NOVOS.items()}
    # capital: o "Adicional de Capital Principal" não tem letra
    for am in novos:
        for l in relatorio(am, "5", ultimo):
            if _primeira_linha(l["NomeColuna"]).startswith("Adicional de Capital Principal") and l.get("Saldo") is not None:
                dados["capital"][am].setdefault(l["CodInst"], {})["=adicional"] = float(l["Saldo"])

    # ---- histórico longo (Resumo, layout antigo e novo) ----
    resumo_hist = {am: _por_instituicao(relatorio(am, "1", ultimo), chave_nome) for am in historico}

    def campo_hist(valores, nomes):
        for n in nomes:
            for k, v in valores.items():
                if k.startswith(n):
                    return v
        return None

    instituicoes = sorted(dados["resumo"][ultimo])
    DIR_BANCOS.mkdir(parents=True, exist_ok=True)
    lista = []
    for cod in instituicoes:
        r_ult = dados["resumo"][ultimo].get(cod, {})
        ativo = r_ult.get("Ativo Total")
        if not ativo:
            continue
        cad = cadastro.get(cod, {})
        id_ = cod.lower()

        def serie(nome, k):
            return [dados[nome][am].get(cod, {}).get(k) for am in novos]

        def tabela(nome, layout, trimestral=False):
            linhas = []
            for k, rotulo, nivel in layout:
                if k.startswith("="):
                    continue
                v = serie(nome, k)
                if trimestral:
                    v = _trimestral(dict(zip(novos, v)), novos)
                linhas.append({"k": k, "r": rotulo, "n": nivel, "v": [None if x is None else round(x, 2) for x in v]})
            return linhas

        dre = tabela("dre", LAYOUT_DRE, trimestral=True)
        por_k = {l["k"]: l["v"] for l in dre}

        def soma(*ks, sinal=None):
            sinal = sinal or [1] * len(ks)
            out = []
            for i in range(len(novos)):
                partes = [por_k.get(k, [None] * len(novos))[i] for k in ks]
                out.append(None if all(p is None for p in partes) else round(sum(s * (p or 0) for s, p in zip(sinal, partes)), 2))
            return out

        calculadas = {"=receitas": soma("a", "b", "c", "d", "e", "i", "j"), "=antes_pdd": soma("k", "f", sinal=[1, -1]),
                      "=antes_part": soma("w", "x")}
        dre_final = []
        for k, rotulo, nivel in LAYOUT_DRE:
            if k in calculadas:
                dre_final.append({"k": k, "r": rotulo, "n": nivel, "v": calculadas[k]})
            else:
                dre_final.append(next(l for l in dre if l["k"] == k))
        capital = []
        for k, rotulo, nivel in LAYOUT_CAPITAL:
            capital.append({"k": k, "r": rotulo, "n": nivel, "indice": k in INDICES_CAPITAL,
                            "v": [None if x is None else round(x, 6 if k in INDICES_CAPITAL else 2) for x in serie("capital", k)]})

        def grupos(nome):
            saida = {}
            for am in novos:
                for chave in dados[nome][am].get(cod, {}):
                    saida.setdefault(chave, None)
            return {chave: [None if x is None else round(x, 2) for x in serie(nome, chave)] for chave in saida}

        datas_hist = [am for am in historico if cod in resumo_hist[am]]
        lucro_hist = {am: campo_hist(resumo_hist[am][cod], ["Lucro Líquido"]) for am in datas_hist}
        hist = {
            "datas": [_iso(am) for am in datas_hist],
            "ativo": [campo_hist(resumo_hist[am][cod], ["Ativo Total"]) for am in datas_hist],
            "carteira": [campo_hist(resumo_hist[am][cod], ["Carteira de Crédito"]) for am in datas_hist],
            "captacoes": [campo_hist(resumo_hist[am][cod], ["Captações"]) for am in datas_hist],
            "pl": [campo_hist(resumo_hist[am][cod], ["Patrimônio Líquido"]) for am in datas_hist],
            "lucro_tri": _trimestral(lucro_hist, datas_hist),
            "basileia": [campo_hist(resumo_hist[am][cod], ["Índice de Basileia"]) for am in datas_hist],
        }
        resumo = {k: serie("resumo", k) for k in ("Ativo Total", "Carteira de Crédito", "Títulos e Valores Mobiliários", "Passivo Exigível",
                                                  "Captações", "Patrimônio Líquido", "Lucro Líquido")}
        resumo["Lucro Líquido"] = _trimestral(dict(zip(novos, resumo["Lucro Líquido"])), novos)
        clientes = grupos("clientes")
        carteiras = grupos("carteiras")
        detalhe = {
            "id": id_, "cod": cod, "nome": cad.get("NomeInstituicao", cod), "segmento": cad.get("Sr"), "tipo_cod": cad.get("Tcb"),
            "tipo": TIPOS.get(cad.get("Tcb"), cad.get("Tcb")), "controle": CONTROLE.get(cad.get("Tc")), "uf": cad.get("Uf"),
            "municipio": cad.get("Municipio"), "atividade": cad.get("Atividade"), "inicio_atividade": cad.get("DataInicioAtividade"),
            "cnpj_lider": cad.get("CnpjInstituicaoLider"), "ticker": LISTADOS.get(cod),
            "trimestres": [_iso(am) for am in novos], "resumo": resumo, "clientes": clientes,
            "ativo": tabela("ativo", LAYOUT_ATIVO), "passivo": tabela("passivo", LAYOUT_PASSIVO), "dre": dre_final, "capital": capital,
            "indexador": grupos("indexador"), "regiao": grupos("regiao"), "porte": grupos("porte"), "carteiras": carteiras,
            "pf": grupos("pf"), "pj": grupos("pj"), "historico": hist,
        }
        (DIR_BANCOS / f"{id_}.json").write_text(json.dumps(detalhe, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

        lucro_tri = resumo["Lucro Líquido"]
        ult4 = [x for x in lucro_tri[-4:] if x is not None]
        lucro_12m = sum(ult4) if len(ult4) == 4 else None
        pl = resumo["Patrimônio Líquido"][-1]
        cap_n = next(l for l in capital if l["k"] == "n")["v"][-1]
        total_cart = (carteiras.get("Total Geral") or [None])[-1]
        inad = (carteiras.get("Inadimplência") or [None])[-1]
        lista.append({
            "id": id_, "cod": cod, "nome": detalhe["nome"], "segmento": detalhe["segmento"], "tipo_cod": detalhe["tipo_cod"],
            "controle": detalhe["controle"], "uf": detalhe["uf"], "ticker": detalhe["ticker"], "ativo": ativo,
            "carteira": resumo["Carteira de Crédito"][-1], "pl": pl, "lucro_12m": lucro_12m,
            "roe": lucro_12m / pl if lucro_12m is not None and pl and pl > 0 else None, "basileia": cap_n,
            "inadimplencia": inad / total_cart if inad is not None and total_cart else None,
        })

    for ticker, (cnpj, nome, tipo) in SO_CVM.items():
        try:
            lista.append(gerar_cvm(ticker, cnpj, nome, tipo))
        except Exception as e:  # o resto da lista segue
            print(f"   ⚠️ {ticker} (CVM): {e!r}")

    ordem_seg = {"S1": 1, "S2": 2, "S3": 3, "S4": 4, "S5": 5}
    lista.sort(key=lambda x: (ordem_seg.get(x["segmento"], 9), -(x["ativo"] or 0)))
    (DIR_DADOS_SITE / "bancos.json").write_text(json.dumps({
        "gerado_em": datetime.now(FUSO_BR).isoformat(timespec="minutes"), "data_base": _iso(ultimo), "trimestres": [_iso(am) for am in novos],
        "instituicoes": lista, "fonte": "Banco Central — IF.data (API Olinda), conglomerados prudenciais e instituições independentes"},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"✅ bancos: {len(lista)} instituições, data-base {_iso(ultimo)}; trimestres {novos[0]}–{novos[-1]}")
    return len(lista)


if __name__ == "__main__":
    gerar()
