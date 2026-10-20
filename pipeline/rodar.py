"""
Orquestrador da atualização diária da R.V. Mapp (roda no GitHub Actions).

- Todo dia: Banco Central/Focus, agenda, Tesouro, curva DI da B3, cotações e proventos,
  notícias e planilhas de Macro e Juros.
- Empresas (JSON + Excel): quando a CVM republica um ZIP, só as empresas que entregaram
  documento novo (ITR/DFP ou reapresentação), pelo índice de documentos da própria CVM.
  Todas: quando ainda não existem arquivos, quando o código dos cálculos mudou, uma vez por
  semana no fim de semana (para o Excel pegar os proventos novos) ou com --tudo.

Uma fonte que falhar não derruba as outras: o erro vai para site/dados/status.json.

Uso: py -m pipeline.rodar [--tudo]
"""

import json
import sys
import traceback
from datetime import date, datetime, timedelta, timezone

from pipeline import DIR_DADOS_SITE, DIR_INTERMEDIARIO, sem_segredos


def _etapa(nome, funcao, status):
    print(f"\n=== {nome} ===", flush=True)
    inicio = datetime.now(timezone.utc)
    try:
        resultado = funcao()
        status[nome] = {"ok": True, "segundos": round((datetime.now(timezone.utc) - inicio).total_seconds())}
        return resultado
    except Exception as e:
        traceback.print_exc()
        status[nome] = {"ok": False, "erro": sem_segredos(repr(e))[:500]}
        return None


ARQUIVOS_QUE_GERAM_EMPRESAS = [
    "src/cvm_itr.py", "src/padrao_visual.py", "src/indicadores.py", "src/exportar.py",
    "pipeline/series_empresa.py", "pipeline/gerar_empresas.py", "config/empresas_selecionadas.csv",
]


def versao_do_codigo():
    """Impressão digital do código que monta JSON/Excel das empresas: mudou -> regerar tudo."""
    import hashlib
    from pipeline import RAIZ
    h = hashlib.sha1()
    for nome in ARQUIVOS_QUE_GERAM_EMPRESAS:
        h.update((RAIZ / nome).read_bytes())
    return h.hexdigest()


ARQ_ENTREGAS = DIR_INTERMEDIARIO / "entregas_processadas.json"


def entregas_cvm(universo):
    """Conjunto 'cnpj|tipo|período|versão' de todos os ITR/DFP entregues pelas empresas da lista (índice dos ZIPs da CVM)."""
    import io
    import zipfile

    import pandas as pd
    from config.config import RAW_DIR
    cnpjs = set(universo["CNPJ_CIA"].str.replace(r"\D", "", regex=True))
    chaves = set()
    for tipo in ("itr", "dfp"):
        for ano in (date.today().year - 1, date.today().year):
            arq = RAW_DIR / f"{tipo}_cia_aberta_{ano}.zip"
            if not arq.exists():
                continue
            with zipfile.ZipFile(arq) as z:
                df = pd.read_csv(io.BytesIO(z.read(f"{tipo}_cia_aberta_{ano}.csv")), sep=";", encoding="latin1",
                                 usecols=["CNPJ_CIA", "DT_REFER", "VERSAO"], dtype=str)
            df["CNPJ"] = df["CNPJ_CIA"].str.replace(r"\D", "", regex=True)
            df = df[df["CNPJ"].isin(cnpjs)]
            chaves |= {f"{c}|{tipo}|{d}|{v}" for c, d, v in zip(df["CNPJ"], df["DT_REFER"], df["VERSAO"])}
    return chaves


def tickers_com_entrega_nova(universo, atuais):
    """Tickers das empresas com documento ainda não processado; None se não há registro anterior (refaz todas)."""
    if not ARQ_ENTREGAS.exists():
        return None
    vistas = set(json.loads(ARQ_ENTREGAS.read_text(encoding="utf-8")))
    cnpjs_novos = {k.split("|")[0] for k in atuais - vistas}
    lista = universo[universo["CNPJ_CIA"].str.replace(r"\D", "", regex=True).isin(cnpjs_novos)]
    return {t for ts in lista["tickers_lista"] for t in ts}


def semanal_pendente(arq):
    """Refação semanal no fim de semana: a primeira execução de sábado ou domingo que ainda não a fez."""
    hoje = date.today()
    if hoje.weekday() < 5:
        return False
    sabado = hoje - timedelta(days=hoje.weekday() - 5)
    return not arq.exists() or arq.read_text().strip() < sabado.isoformat()


def main(tudo=False):
    from pipeline import (agenda, bancos, calendario_resultados, credito, curva_di, eleicoes, eventos, ficha, fre_textos, macro, mercado, noticias,
                          offshore, planilhas, resumos, tesouro)
    from pipeline.cvm_lote import atualizar_base_cvm
    from pipeline.gerar_empresas import DIR_EMPRESAS, gerar_indice
    from pipeline.gerar_empresas import main as gerar_empresas
    from src.screening import universo_selecionado

    status = {}
    _etapa("macro", macro.gerar, status)
    _etapa("credito", credito.gerar, status)
    _etapa("agenda", agenda.gerar, status)
    _etapa("tesouro", tesouro.gerar, status)
    _etapa("curva_di", curva_di.gerar, status)
    _etapa("mercado", mercado.gerar, status)
    _etapa("noticias", noticias.gerar, status)
    _etapa("offshore", offshore.gerar, status)
    _etapa("eleicoes", eleicoes.gerar, status)
    _etapa("bancos", bancos.gerar, status)
    _etapa("planilhas", planilhas.gerar, status)
    _etapa("eventos", eventos.gerar, status)
    _etapa("ficha", ficha.gerar, status)
    _etapa("fre_textos", fre_textos.gerar, status)
    _etapa("resumos", resumos.gerar, status)

    cnpjs = set(universo_selecionado()["CNPJ_CIA"].str.replace(r"\D", "", regex=True))
    reprocessados = _etapa("cvm_base", lambda: atualizar_base_cvm(cnpjs), status) or []
    sem_arquivos = not any(DIR_EMPRESAS.glob("*.json"))
    arq_versao = DIR_INTERMEDIARIO / "versao_codigo_empresas.txt"
    versao = versao_do_codigo()
    codigo_mudou = not arq_versao.exists() or arq_versao.read_text() != versao
    arq_semanal = DIR_INTERMEDIARIO / "ultima_atualizacao_semanal_empresas.txt"
    semanal = semanal_pendente(arq_semanal)
    universo = universo_selecionado()
    atuais = entregas_cvm(universo)
    if tudo or sem_arquivos or codigo_mudou or semanal:
        motivo = ("tudo" if tudo else "sem arquivos" if sem_arquivos else "código mudou" if codigo_mudou
                  else "atualização semanal (fim de semana)")
        print(f"Gerando todas as empresas ({motivo})")
        _etapa("empresas", gerar_empresas, status)
    elif reprocessados:
        novos = tickers_com_entrega_nova(universo, atuais)
        if novos is None:  # primeira vez: os arquivos já existem e estão em dia; só cria o registro das entregas
            print("Registro das entregas da CVM criado; a partir da próxima atualização só as empresas com documento novo são refeitas")
            ARQ_ENTREGAS.write_text(json.dumps(sorted(atuais)), encoding="utf-8")
        elif novos:
            print(f"CVM atualizada: gerando só {len(novos)} papéis com documento novo: {sorted(novos)}")
            _etapa("empresas", lambda: gerar_empresas(filtro=novos), status)
        else:
            print("CVM republicou os arquivos, mas nenhuma empresa da lista entregou documento novo")
    if status.get("empresas", {}).get("ok"):
        ARQ_ENTREGAS.write_text(json.dumps(sorted(atuais)), encoding="utf-8")
    if status.get("empresas", {}).get("ok") and (tudo or sem_arquivos or codigo_mudou or semanal):
        arq_versao.write_text(versao)
        if date.today().weekday() >= 5:  # qualquer refação completa no fim de semana já vale como a semanal
            arq_semanal.write_text(date.today().isoformat())
    _etapa("indice", gerar_indice, status)
    _etapa("calendario_resultados", calendario_resultados.gerar, status)  # usa os ZIPs da CVM e o índice de empresas

    status_final = {"atualizado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "cvm_reprocessados": [f"{f} {a}" for f, a in reprocessados], "etapas": status}
    (DIR_DADOS_SITE / "status.json").write_text(json.dumps(status_final, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(status_final, ensure_ascii=False, indent=1))

    # Sem índice de empresas o site não funciona: aí sim a execução falha
    if not (DIR_DADOS_SITE / "empresas.json").exists():
        sys.exit(1)


if __name__ == "__main__":
    main(tudo="--tudo" in sys.argv)
