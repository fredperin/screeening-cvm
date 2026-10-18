"""
Orquestrador da atualização diária da R.V. Mapp (roda no GitHub Actions).

- Todo dia: Banco Central/Focus, Tesouro, curva DI da B3, cotações e proventos.
- Empresas (JSON + Excel): só quando a CVM republicou algum ZIP, quando ainda não
  existem arquivos gerados, às segundas-feiras (para o Excel pegar os proventos
  novos) ou com --tudo.

Uma fonte que falhar não derruba as outras: o erro vai para site/dados/status.json.

Uso: py -m pipeline.rodar [--tudo]
"""

import json
import sys
import traceback
from datetime import date, datetime, timezone

from pipeline import DIR_DADOS_SITE, DIR_INTERMEDIARIO


def _etapa(nome, funcao, status):
    print(f"\n=== {nome} ===", flush=True)
    inicio = datetime.now(timezone.utc)
    try:
        resultado = funcao()
        status[nome] = {"ok": True, "segundos": round((datetime.now(timezone.utc) - inicio).total_seconds())}
        return resultado
    except Exception as e:
        traceback.print_exc()
        status[nome] = {"ok": False, "erro": repr(e)[:500]}
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


def main(tudo=False):
    from pipeline import agenda, curva_di, eventos, ficha, fre_textos, macro, mercado, resumos, tesouro
    from pipeline.cvm_lote import atualizar_base_cvm
    from pipeline.gerar_empresas import DIR_EMPRESAS, gerar_indice
    from pipeline.gerar_empresas import main as gerar_empresas
    from src.screening import universo_selecionado

    status = {}
    _etapa("macro", macro.gerar, status)
    _etapa("agenda", agenda.gerar, status)
    _etapa("tesouro", tesouro.gerar, status)
    _etapa("curva_di", curva_di.gerar, status)
    _etapa("mercado", mercado.gerar, status)
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
    if tudo or reprocessados or sem_arquivos or codigo_mudou or date.today().weekday() == 0:
        motivo = ("tudo" if tudo else "cvm atualizada" if reprocessados else "sem arquivos" if sem_arquivos
                  else "código mudou" if codigo_mudou else "atualização semanal")
        print(f"Gerando empresas ({motivo}); ZIPs reprocessados: {reprocessados}")
        _etapa("empresas", gerar_empresas, status)
        if status.get("empresas", {}).get("ok"):
            arq_versao.write_text(versao)
    _etapa("indice", gerar_indice, status)

    status_final = {"atualizado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "cvm_reprocessados": [f"{f} {a}" for f, a in reprocessados], "etapas": status}
    (DIR_DADOS_SITE / "status.json").write_text(json.dumps(status_final, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(status_final, ensure_ascii=False, indent=1))

    # Sem índice de empresas o site não funciona: aí sim a execução falha
    if not (DIR_DADOS_SITE / "empresas.json").exists():
        sys.exit(1)


if __name__ == "__main__":
    main(tudo="--tudo" in sys.argv)
