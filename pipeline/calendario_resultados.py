"""
Calendário de resultados das empresas da lista: próximo ITR/DFP de cada uma.

Base oficial: índice de documentos dos arquivos ITR e DFP da CVM (data em que cada empresa entregou
cada trimestre, a primeira versão). Para o próximo período ainda não entregue:
- prazo legal: ITR até 45 dias depois do fim do trimestre; DFP até 3 meses depois do fim do exercício;
- data estimada: a data em que a empresa entregou o mesmo período do ano anterior, um ano depois
  (mesmo dia da semana), limitada ao prazo legal. É uma estimativa pelo histórico, não a data oficial
  divulgada pela empresa.

Saída: site/dados/calendario_resultados.json. Uso: py -m pipeline.calendario_resultados
"""

import io
import json
import zipfile
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from config.config import RAW_DIR
from pipeline import DIR_DADOS_SITE

FUSO_BR = timezone(timedelta(hours=-3))


def _indice(tipo, ano):
    arq = RAW_DIR / f"{tipo}_cia_aberta_{ano}.zip"
    if not arq.exists():
        return pd.DataFrame()
    with zipfile.ZipFile(arq) as z:
        df = pd.read_csv(io.BytesIO(z.read(f"{tipo}_cia_aberta_{ano}.csv")), sep=";", encoding="latin1",
                         usecols=["CNPJ_CIA", "DT_REFER", "VERSAO", "DT_RECEB"])
    df["TIPO"] = tipo.upper()
    return df


def _fim_do_mes(d):
    return (pd.Timestamp(d) + pd.offsets.MonthEnd(0)).date()


def gerar():
    hoje = date.today()
    anos = range(hoje.year - 2, hoje.year + 1)
    entregas = pd.concat([_indice(t, a) for t in ("itr", "dfp") for a in anos], ignore_index=True)
    entregas["CNPJ"] = entregas["CNPJ_CIA"].str.replace(r"\D", "", regex=True)
    entregas["DT_REFER"] = pd.to_datetime(entregas["DT_REFER"]).dt.date
    entregas["DT_RECEB"] = pd.to_datetime(entregas["DT_RECEB"]).dt.date
    # primeira entrega de cada período (reapresentações posteriores não contam como divulgação)
    primeira = entregas.sort_values("DT_RECEB").drop_duplicates(["CNPJ", "DT_REFER"], keep="first")

    indice = json.loads((DIR_DADOS_SITE / "empresas.json").read_text(encoding="utf-8"))
    linhas = []
    for e in indice:
        cnpj = "".join(ch for ch in str(e.get("cnpj", "")) if ch.isdigit())
        h = primeira[primeira["CNPJ"] == cnpj].sort_values("DT_REFER")
        if h.empty:
            continue
        mes_fim = int(h[h["TIPO"] == "DFP"]["DT_REFER"].iloc[-1].month) if (h["TIPO"] == "DFP").any() else 12
        ultimo = h.iloc[-1]
        proximo = _fim_do_mes(pd.Timestamp(ultimo["DT_REFER"]) + pd.DateOffset(months=3))
        dfp = proximo.month == mes_fim
        prazo = _fim_do_mes(pd.Timestamp(proximo) + pd.DateOffset(months=3)) if dfp else proximo + timedelta(days=45)
        ano_antes = h[h["DT_REFER"] == _fim_do_mes(pd.Timestamp(proximo) - pd.DateOffset(years=1))]
        estimada, base = None, None
        if not ano_antes.empty:
            base = ano_antes["DT_RECEB"].iloc[0]
            estimada = min(base + timedelta(days=364), prazo)  # um ano depois, mesmo dia da semana
            if estimada < hoje:
                estimada = None  # pela regra já deveria ter saído: fica só o prazo legal
        linhas.append({
            "id": e["id"], "nome": e["nome"], "ultimo_periodo": ultimo["DT_REFER"].isoformat(),
            "ultimo_divulgado_em": ultimo["DT_RECEB"].isoformat(),
            "proximo_periodo": proximo.isoformat(), "documento": "DFP" if dfp else "ITR",
            "data_estimada": estimada.isoformat() if estimada else None, "base_ano_anterior": base.isoformat() if base else None,
            "prazo_legal": prazo.isoformat(), "atrasado": hoje > prazo,
        })
    linhas.sort(key=lambda l: (l["data_estimada"] or l["prazo_legal"], l["id"]))
    (DIR_DADOS_SITE / "calendario_resultados.json").write_text(json.dumps({
        "gerado_em": datetime.now(FUSO_BR).isoformat(timespec="minutes"), "empresas": linhas,
        "fonte": "CVM — índice de documentos ITR/DFP (data de entrega); estimativa pelo histórico de cada empresa",
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"✅ calendário de resultados: {len(linhas)} empresas; próximos: "
          + ", ".join(f"{l['id']} {l['data_estimada'] or l['prazo_legal']}" for l in linhas[:5]))
    return len(linhas)


if __name__ == "__main__":
    gerar()
