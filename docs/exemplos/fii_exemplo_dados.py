"""Exemplo (protótipo) da página de um FII de tijolo: HGLG11, com os informes da CVM e cotação/rendimentos da Yahoo."""
import io, json, os, sys, zipfile
import pandas as pd

PASTA = os.path.join(os.environ["TMP"], "fii")
DESTINO = sys.argv[1]
CNPJ, TICKER = "11.728.688/0001-47", "HGLG11"


def ler(zipname, nome):
    z = zipfile.ZipFile(os.path.join(PASTA, zipname))
    d = pd.read_csv(io.BytesIO(z.read(nome)), sep=";", encoding="latin1", dtype=str)
    return d[d["CNPJ_Fundo_Classe"] == CNPJ]


num = lambda s: pd.to_numeric(s, errors="coerce")  # noqa: E731

geral = pd.concat([ler(f"m{a}.zip", f"inf_mensal_fii_geral_{a}.csv") for a in (2023, 2024, 2025, 2026)])
comp = pd.concat([ler(f"m{a}.zip", f"inf_mensal_fii_complemento_{a}.csv") for a in (2023, 2024, 2025, 2026)])
ap = pd.concat([ler(f"m{a}.zip", f"inf_mensal_fii_ativo_passivo_{a}.csv") for a in (2023, 2024, 2025, 2026)])
for d in (geral, comp, ap):
    d["Versao"] = num(d["Versao"])
    d.sort_values(["Data_Referencia", "Versao"], inplace=True)
    d.drop_duplicates("Data_Referencia", keep="last", inplace=True)

g = geral.ffill().iloc[-1].fillna("—")  # último valor preenchido de cada campo
cadastro = {"nome": g["Nome_Fundo_Classe"], "cnpj": CNPJ, "ticker": TICKER, "isin": g["Codigo_ISIN"], "administrador": g["Nome_Administrador"],
            "segmento": g["Segmento_Atuacao"], "mandato": g["Mandato"], "gestao": g["Tipo_Gestao"], "publico": g["Publico_Alvo"],
            "inicio": g["Data_Funcionamento"], "site": g["Site"]}

c = comp
mensal = {"datas": c["Data_Referencia"].tolist(),
          "pl": num(c["Patrimonio_Liquido"]).round(0).tolist(), "ativo": num(c["Valor_Ativo"]).round(0).tolist(),
          "cotas": num(c["Cotas_Emitidas"]).tolist(), "vp_cota": num(c["Valor_Patrimonial_Cotas"]).round(4).tolist(),
          "cotistas": num(c["Total_Numero_Cotistas"]).tolist(),
          "dy_mes": (num(c["Percentual_Dividend_Yield_Mes"]) * 100).round(3).tolist(),
          "rent_efetiva": (num(c["Percentual_Rentabilidade_Efetiva_Mes"]) * 100).round(3).tolist(),
          "rent_patrimonial": (num(c["Percentual_Rentabilidade_Patrimonial_Mes"]) * 100).round(3).tolist(),
          "taxa_adm": (num(c["Percentual_Despesas_Taxa_Administracao"]) * 100).round(3).tolist()}

a = ap.iloc[-1]
v = lambda k: float(num(pd.Series([a.get(k)])).fillna(0).iloc[0])  # noqa: E731
composicao = {"data": a["Data_Referencia"], "itens": [
    ["Imóveis prontos para renda", v("Imoveis_Renda_Acabados")], ["Imóveis em construção", v("Imoveis_Renda_Construcao")],
    ["Terrenos", v("Terrenos")], ["Participação em sociedades (SPEs)", v("Acoes_Sociedades_Atividades_FII") + v("Cotas_Sociedades_Atividades_FII")],
    ["Cotas de outros FIIs", v("FII")], ["CRI / CRA", v("CRI_CRA") + v("CRI")], ["Caixa e renda fixa", v("Total_Necessidades_Liquidez")],
    ["Valores a receber", v("Valores_Receber")]],
    "passivo": [["Obrigações de securitização (CRI emitido)", v("Obrigacoes_Securitizacao_Recebiveis")], ["Aquisição de imóveis a pagar", v("Obrigacoes_Aquisicao_Imoveis")],
                ["Rendimentos a distribuir", v("Rendimentos_Distribuir")], ["Outros", v("Outros_Valores_Pagar") + v("Taxa_Administracao_Pagar")]],
    "total_passivo": v("Total_Passivo")}

im = pd.concat([ler(f"t{a}.zip", f"inf_trimestral_fii_imovel_{a}.csv") for a in (2025, 2026)])
im = im[im["Classe"].str.contains("renda acabados", case=False, na=False)]
for k in ("Area", "Percentual_Vacancia", "Percentual_Inadimplencia", "Percentual_Receitas_FII"):
    im[k] = num(im[k])
trimestral = []
for data, x in im.groupby("Data_Referencia"):
    trimestral.append({"data": data, "imoveis": len(x), "area": round(float(x["Area"].sum())),
                       "vacancia_fisica": round(float((x["Area"] * x["Percentual_Vacancia"]).sum() / x["Area"].sum() * 100), 2),
                       "inadimplencia": round(float((x["Percentual_Receitas_FII"] * x["Percentual_Inadimplencia"]).sum() / x["Percentual_Receitas_FII"].sum() * 100), 2)})
ult = im[im["Data_Referencia"] == im["Data_Referencia"].max()].sort_values("Percentual_Receitas_FII", ascending=False)
imoveis = [{"nome": r.Nome_Imovel, "endereco": r.Endereco, "area": r.Area, "vacancia": round(r.Percentual_Vacancia * 100, 1),
            "inadimplencia": round(r.Percentual_Inadimplencia * 100, 1), "receita": round(r.Percentual_Receitas_FII * 100, 2)} for r in ult.itertuples()]

inq = ler("t2026.zip", "inf_trimestral_fii_imovel_renda_acabado_inquilino_2026.csv")
inq = inq[inq["Data_Referencia"] == inq["Data_Referencia"].max()]
setores = (num(inq["Percentual_Receitas_FII"]).groupby(inq["Setor_Atuacao"]).sum() * 100).sort_values(ascending=False).round(1)

y = json.load(open(os.path.join(PASTA, "yahoo_hglg.json")))
fn = json.load(open(os.path.join(PASTA, "fnet.json"), encoding="utf-8"))["data"]
documentos = [{"data": x["dataEntrega"], "referencia": x.get("dataReferencia"), "categoria": (x.get("categoriaDocumento") or "").strip(),
               "tipo": (x.get("tipoDocumento") or "").strip(), "assunto": (x.get("informacoesAdicionais") or "").strip(),
               "link": f"https://fnet.bmfbovespa.com.br/fnet/publico/exibirDocumento?id={x['id']}"} for x in fn]
saida = {"cadastro": cadastro, "mensal": mensal, "composicao": composicao, "trimestral": trimestral, "imoveis": imoveis,
         "imoveis_data": im["Data_Referencia"].max(), "setores_inquilinos": [[k, float(v)] for k, v in setores.items()],
         "documentos": documentos, "cotacao": {"datas": y["cot"]["datas"], "fechamento": y["cot"]["fech"]}, "rendimentos": y["div"],
         "fontes": {"cvm": "CVM — informes mensal e trimestral de FII (dados abertos)", "fnet": "Fundos.NET (B3/CVM) — documentos", "mercado": "Yahoo Finance (cotação e rendimentos, não oficial)"}}
os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
json.dump(saida, open(DESTINO, "w", encoding="utf-8"), ensure_ascii=False, allow_nan=False, default=str)
print("ok", len(mensal["datas"]), "meses;", len(imoveis), "imóveis;", trimestral[-1], setores.head(4).to_dict())
