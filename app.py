"""
app.py — Central de downloads: interface web local para gerar o documento
padrão (DRE + Balanço + DFC) de qualquer empresa não financeira, sem precisar
abrir terminal ou editor de código.

Uso: clique duas vezes em "Iniciar_App.bat" (ou rode `py -m streamlit run app.py`).
"""

import contextlib
import io
from datetime import date

import streamlit as st

from src.cvm_itr import (
    buscar_itr, buscar_dados_cadastrais, buscar_dados_fca, listar_todas_empresas, montar_documento_padrao,
)
from src.exportar import exportar_documento_padrao

st.set_page_config(page_title="Central de Downloads — Dados CVM", page_icon="📊", layout="centered")

ANO_ATUAL = date.today().year
ANO_MAIS_ANTIGO = 2011


@st.cache_data(show_spinner="Carregando lista de empresas da CVM...")
def carregar_empresas() -> tuple[list, dict]:
    """
    Busca a lista de empresas no ano mais recente disponível. Se o ano
    corrente ainda não tiver ITR publicado, cai automaticamente pro anterior.
    Retorna (lista_de_rotulos_ordenada, {rotulo: cnpj}).
    """
    for ano in (ANO_ATUAL, ANO_ATUAL - 1):
        try:
            empresas = listar_todas_empresas(ano)
            if not empresas.empty:
                rotulos = [f"{row.DENOM_CIA} — {row.CNPJ_CIA}" for row in empresas.itertuples()]
                mapa = {r: c for r, c in zip(rotulos, empresas["CNPJ_CIA"])}
                return rotulos, mapa
        except Exception:
            continue
    return [], {}


st.title("📊 Central de Downloads — Dados CVM")
st.caption(
    "Gera um Excel com DRE, Balanço Patrimonial e DFC de qualquer empresa não "
    "financeira listada na CVM, no padrão do projeto (cores, contas principais, "
    "períodos alinhados)."
)

rotulos, mapa_cnpj = carregar_empresas()

if not rotulos:
    st.error("Não foi possível carregar a lista de empresas da CVM agora. Verifique sua conexão e recarregue a página.")
    st.stop()

rotulo_escolhido = st.selectbox(
    "Empresa (digite para buscar)",
    options=rotulos,
    index=None,
    placeholder="Comece a digitar o nome da empresa...",
)

col1, col2 = st.columns(2)
with col1:
    ano_inicio = st.number_input("Ano inicial", min_value=ANO_MAIS_ANTIGO, max_value=ANO_ATUAL, value=ANO_ATUAL - 9)
with col2:
    ano_fim = st.number_input("Ano final", min_value=ANO_MAIS_ANTIGO, max_value=ANO_ATUAL, value=ANO_ATUAL)

tipo = st.radio("Tipo de demonstração", options=["con", "ind"], format_func=lambda t: "Consolidado (padrão)" if t == "con" else "Individual", horizontal=True)

gerar = st.button("Gerar relatório", type="primary", disabled=(rotulo_escolhido is None))

if gerar and rotulo_escolhido:
    if ano_inicio > ano_fim:
        st.error("O ano inicial não pode ser maior que o ano final.")
        st.stop()

    cnpj = mapa_cnpj[rotulo_escolhido]
    nome_empresa = rotulo_escolhido.split(" — ")[0]
    anos = list(range(int(ano_inicio), int(ano_fim) + 1))

    captura = io.StringIO()
    caminho_arquivo = None
    erro = None

    with st.spinner(f"Buscando dados de {nome_empresa} na CVM... (pode levar alguns minutos na primeira vez)"):
        try:
            with contextlib.redirect_stdout(captura):
                demonstracoes = buscar_itr(cnpj, anos, tipo=tipo)
                blocos = montar_documento_padrao(demonstracoes, ano_inicio=int(ano_inicio))
                dados_cadastrais = {**buscar_dados_cadastrais(cnpj), **buscar_dados_fca(cnpj)}
                caminho_arquivo = exportar_documento_padrao(
                    blocos, nome_empresa, int(ano_inicio), int(ano_fim), dados_cadastrais=dados_cadastrais,
                )
        except Exception as e:
            erro = e

    if erro:
        st.error(f"Deu erro ao gerar o relatório: {erro}")
    else:
        st.success(f"Relatório de {nome_empresa} gerado com sucesso!")

        # A Central de Downloads não guarda cópia em data/processed/ — só
        # entrega pelo botão. O arquivo é lido pra memória e apagado do disco
        # na hora, senão cada busca ad-hoc pelo site iria acumular um Excel
        # permanente na pasta do projeto.
        with open(caminho_arquivo, "rb") as f:
            dados_arquivo = f.read()
        caminho_arquivo.unlink()

        st.download_button(
            "⬇️ Baixar Excel",
            data=dados_arquivo,
            file_name=caminho_arquivo.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with st.expander("Ver detalhes do processamento (avisos, períodos descartados, etc.)"):
        st.text(captura.getvalue() or "(sem mensagens)")
