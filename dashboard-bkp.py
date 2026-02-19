import streamlit as st
import pandas as pd
import plotly.express as px
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
import os

st.set_page_config(page_title="BI Condomínio", layout="wide")

st.title("🏢 Dashboard Financeiro do Condomínio")

# ==========================
# CARREGAR DADOS
# ==========================
df = pd.read_csv("dados_condominio.csv")
df = df.sort_values("mes")

meses = sorted(df["mes"].unique())

# ==========================
# FILTROS
# ==========================
st.sidebar.header("Filtros")

mes_atual = st.sidebar.selectbox("Mês Atual", meses, index=len(meses)-1)
mes_anterior = st.sidebar.selectbox("Mês Comparação", meses, index=len(meses)-2)

limite_alerta = st.sidebar.slider(
    "Alerta de aumento acima de (%)",
    0, 100, 10
)

itens_disponiveis = df["item"].unique()
filtro_item = st.sidebar.multiselect("Filtrar Itens", itens_disponiveis)

# ==========================
# PREPARAÇÃO
# ==========================
df_atual = df[df["mes"] == mes_atual]
df_ant = df[df["mes"] == mes_anterior]

comparacao = df_atual.merge(
    df_ant,
    on="item",
    suffixes=("_atual", "_anterior")
)

comparacao["diferenca"] = comparacao["valor_atual"] - comparacao["valor_anterior"]
comparacao["percentual"] = (
    comparacao["diferenca"] / comparacao["valor_anterior"]
) * 100

if filtro_item:
    comparacao = comparacao[comparacao["item"].isin(filtro_item)]

# ==========================
# KPIs
# ==========================
total_atual = df_atual["valor"].sum()
total_anterior = df_ant["valor"].sum()
variacao_total = total_atual - total_anterior
percentual_total = (variacao_total / total_anterior) * 100

col1, col2, col3 = st.columns(3)

col1.metric("💰 Total Atual", f"R$ {total_atual:,.2f}")
col2.metric("📅 Total Anterior", f"R$ {total_anterior:,.2f}")
col3.metric(
    "📈 Variação Total",
    f"R$ {variacao_total:,.2f}",
    f"{percentual_total:.2f}%"
)

st.divider()

# ==========================
# ALERTA
# ==========================
alertas = comparacao[comparacao["percentual"] > limite_alerta]

if not alertas.empty:
    st.error("🚨 Itens com aumento acima do limite:")
    st.dataframe(alertas[["item", "percentual"]])

# ==========================
# GRÁFICO EXECUTIVO - TOP AUMENTOS
# ==========================
st.subheader("📊 Top 5 Maiores Aumentos")

top_aumentos = (
    comparacao
    .sort_values("diferenca", ascending=False)
    .head(5)
)

fig1 = px.bar(
    top_aumentos,
    y="item",
    x="diferenca",
    orientation="h",
    text="diferenca",
    color="diferenca",
    color_continuous_scale="Reds"
)

fig1.update_layout(
    yaxis_title="",
    xaxis_title="Aumento (R$)",
    height=400
)

fig1.update_traces(texttemplate="R$ %{text:.2f}")

st.plotly_chart(fig1, use_container_width=True)


# ==========================
# GRÁFICO EXECUTIVO - REDUÇÕES
# ==========================
st.subheader("📉 Itens que Reduziram")

reducoes = (
    comparacao
    .sort_values("diferenca")
    .head(5)
)

fig2 = px.bar(
    reducoes,
    y="item",
    x="diferenca",
    orientation="h",
    text="diferenca",
    color="diferenca",
    color_continuous_scale="Greens"
)

fig2.update_layout(
    yaxis_title="",
    xaxis_title="Redução (R$)",
    height=400
)

fig2.update_traces(texttemplate="R$ %{text:.2f}")

st.plotly_chart(fig2, use_container_width=True)


# ==========================
# GRÁFICO PIZZA
# ==========================
st.subheader("🥧 Composição do Mês Atual")

fig2 = px.pie(
    df_atual,
    names="item",
    values="valor",
    title="Distribuição das Despesas"
)

st.plotly_chart(fig2, use_container_width=True)

# ==========================
# EVOLUÇÃO MENSAL
# ==========================
st.subheader("📈 Evolução Total Mensal")

total_mes = df.groupby("mes")["valor"].sum().reset_index()

fig3 = px.line(
    total_mes,
    x="mes",
    y="valor",
    markers=True,
    title="Evolução do Total Mensal"
)

st.plotly_chart(fig3, use_container_width=True)

# ==========================
# TABELA
# ==========================
st.subheader("📋 Tabela Comparativa")

st.dataframe(
    aumentos[[
        "item",
        "valor_anterior",
        "valor_atual",
        "diferenca",
        "percentual"
    ]],
    use_container_width=True
)

# ==========================
# EXPORTAR PDF
# ==========================
if st.button("📥 Exportar Relatório PDF"):

    pdf_path = "relatorio_condominio.pdf"
    doc = SimpleDocTemplate(pdf_path)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("Relatório Financeiro Condomínio", styles["Heading1"]))
    elements.append(Spacer(1, 0.5 * inch))

    data = [["Item", "Anterior", "Atual", "Diferença", "%"]]

    for _, row in aumentos.iterrows():
        data.append([
            row["item"],
            f"{row['valor_anterior']:.2f}",
            f"{row['valor_atual']:.2f}",
            f"{row['diferenca']:.2f}",
            f"{row['percentual']:.2f}%"
        ])

    tabela = Table(data)
    tabela.setStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
    ])

    elements.append(tabela)
    doc.build(elements)

    st.success("Relatório gerado com sucesso!")
    st.download_button(
        "Baixar PDF",
        open(pdf_path, "rb"),
        file_name="relatorio_condominio.pdf"
    )
