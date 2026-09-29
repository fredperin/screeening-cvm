"""
1_Screening.py — Dashboard de screening: visão de cima de todas as empresas
não financeiras da B3, com filtros, pra achar candidatas antes de aprofundar
na Central de Downloads.

Lê um CSV pré-calculado (data/screening/screening_atual.csv) em vez de rodar
o pipeline ao vivo — buscar ~280 empresas no yfinance leva minutos, o que não
dá pra fazer a cada acesso ao site. O CSV é atualizado periodicamente rodando
`py rodar_screening.py` e enviando o resultado pro repositório.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Screening — Dados CVM", page_icon="🔎", layout="wide")

CAMINHO_CSV = Path(__file__).resolve().parent.parent / "data" / "screening" / "screening_atual.csv"
CAMINHO_DATA = CAMINHO_CSV.parent / "ultima_atualizacao.txt"


@st.cache_data
def carregar_screening() -> pd.DataFrame:
    return pd.read_csv(CAMINHO_CSV)


st.title("🔎 Screening — Empresas Não Financeiras (B3)")

if not CAMINHO_CSV.exists():
    st.error(
        "Ainda não há um screening gerado. Rode `py rodar_screening.py` localmente "
        "e envie o resultado (data/screening/) pro repositório."
    )
    st.stop()

df = carregar_screening()

if CAMINHO_DATA.exists():
    st.caption(f"Última atualização: {CAMINHO_DATA.read_text(encoding='utf-8').strip()} — {len(df)} empresas")

# --- Filtros ---
with st.sidebar:
    st.header("Filtros")

    setores = sorted(df["Setor"].dropna().unique())
    setores_escolhidos = st.multiselect("Setor", options=setores, default=[])

    cap_min, cap_max = float(df["Market Cap (R$)"].min(skipna=True) or 0), float(df["Market Cap (R$)"].max(skipna=True) or 1)
    faixa_cap_bi = st.slider(
        "Market Cap (R$ bilhões)",
        min_value=0.0, max_value=round(cap_max / 1e9, 1) + 1,
        value=(0.0, round(cap_max / 1e9, 1) + 1),
    )

    roe_min = st.number_input("ROE mínimo (%)", value=-999.0, step=1.0)
    dy_min = st.number_input("Dividend Yield mínimo (%)", value=0.0, step=0.5)
    pl_max = st.number_input("P/L máximo (deixe alto p/ não filtrar)", value=9999.0, step=1.0)
    crescimento_min = st.number_input("Crescimento de Receita mínimo (%)", value=-999.0, step=1.0)

    apenas_com_dados = st.checkbox("Só empresas com dados de mercado completos", value=True)

# --- Aplicação dos filtros ---
filtrado = df.copy()

if setores_escolhidos:
    filtrado = filtrado[filtrado["Setor"].isin(setores_escolhidos)]

if apenas_com_dados:
    filtrado = filtrado[filtrado["Preço (R$)"].notna()]

filtrado = filtrado[
    (filtrado["Market Cap (R$)"].isna() | filtrado["Market Cap (R$)"].between(faixa_cap_bi[0] * 1e9, faixa_cap_bi[1] * 1e9))
    & (filtrado["ROE (%)"].isna() | (filtrado["ROE (%)"] >= roe_min))
    & (filtrado["Dividend Yield (%)"].isna() | (filtrado["Dividend Yield (%)"] >= dy_min))
    & (filtrado["P/L"].isna() | (filtrado["P/L"] <= pl_max))
    & (filtrado["Crescimento Receita (%)"].isna() | (filtrado["Crescimento Receita (%)"] >= crescimento_min))
]

st.subheader(f"{len(filtrado)} empresas encontradas")

st.dataframe(
    filtrado.sort_values("Market Cap (R$)", ascending=False, na_position="last"),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Preço (R$)": st.column_config.NumberColumn(format="%.2f"),
        "Market Cap (R$)": st.column_config.NumberColumn(format="%.0f"),
        "P/L": st.column_config.NumberColumn(format="%.2f"),
        "P/VP": st.column_config.NumberColumn(format="%.2f"),
        "Dividend Yield (%)": st.column_config.NumberColumn(format="%.2f"),
        "ROE (%)": st.column_config.NumberColumn(format="%.2f"),
        "Margem Bruta (%)": st.column_config.NumberColumn(format="%.2f"),
        "Margem Líquida (%)": st.column_config.NumberColumn(format="%.2f"),
        "Crescimento Receita (%)": st.column_config.NumberColumn(format="%.2f"),
    },
)

st.download_button(
    "⬇️ Baixar tabela filtrada (CSV)",
    data=filtrado.to_csv(index=False).encode("utf-8-sig"),
    file_name="screening_filtrado.csv",
    mime="text/csv",
)

# --- Gráfico: P/L x Crescimento de Receita ---
grafico_df = filtrado.dropna(subset=["P/L", "Crescimento Receita (%)"])
if not grafico_df.empty:
    st.subheader("P/L × Crescimento de Receita")
    st.scatter_chart(grafico_df, x="Crescimento Receita (%)", y="P/L", size="Market Cap (R$)", color="Setor")

st.caption(
    "Simplificações desse screening: Receita/Lucro usam o último ano fiscal completo "
    "(não um LTM trimestral); Ativo/Passivo/PL usam o balanço mais recente disponível. "
    "Veja o código-fonte (src/screening.py) para os detalhes."
)
