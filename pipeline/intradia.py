"""
Atualização leve ao longo do dia (3x, dias úteis): só o Tesouro Direto e a planilha de Juros.
Reaproveita o CSV oficial do Tesouro Transparente já baixado na atualização diária e busca os
preços do momento no site do Tesouro Direto (bloco "tempo real", não oficial e separado).

Uso: py -m pipeline.intradia
"""

import json
import sys
from datetime import datetime, timezone

from pipeline import DIR_DADOS_SITE


def main():
    from pipeline import planilhas, tesouro

    inicio = datetime.now(timezone.utc)
    erro = None
    try:
        tesouro.gerar(baixar_arquivo=not tesouro.ARQ.exists())
        planilhas.gerar_juros()
    except Exception as e:
        erro = repr(e)[:500]
        print("❌", erro)

    # registra no status.json da atualização diária, para aparecer na página Status dos dados
    arq = DIR_DADOS_SITE / "status.json"
    status = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {"etapas": {}}
    tes = json.loads((DIR_DADOS_SITE / "tesouro.json").read_text(encoding="utf-8"))
    status["etapas"]["tesouro_intradia"] = {
        "ok": erro is None and not tes.get("falha_tempo_real"), "segundos": round((datetime.now(timezone.utc) - inicio).total_seconds()),
        "em": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "precificado_em": (tes.get("tempo_real") or {}).get("precificado_em"),
        **({"erro": erro or tes.get("falha_tempo_real")} if erro or tes.get("falha_tempo_real") else {}),
    }
    arq.write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
    tr = tes.get("tempo_real")
    print(f"✅ Tesouro: oficial de {tes['data_base']}; tempo real (não oficial) " + (f"às {tr['precificado_em']}" if tr else "indisponível"))
    if erro:
        sys.exit(1)


if __name__ == "__main__":
    main()
