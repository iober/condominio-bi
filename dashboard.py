import streamlit as st
import pandas as pd
import plotly.express as px
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from google_login import is_authenticated, handle_callback, show_login_page, logout, inject_cookie_reader, _set_cookie_js
from extrair_dados import buscar_e_extrair

st.set_page_config(page_title="BI Condomínio", layout="wide")

# ==========================
# AUTENTICAÇÃO
# ==========================
# 1. Injeta JS para ler cookie e redirecionar com ?sid= se necessário
inject_cookie_reader()

# 2. Processar callback do Google OAuth
if "code" in st.query_params:
    if handle_callback():
        sid = st.query_params.get("sid", "")
        if sid:
            _set_cookie_js(sid)  # Grava cookie no navegador
    st.rerun()

if not is_authenticated():
    show_login_page()

# ==========================
# CARREGAR DADOS DO GMAIL
# ==========================
@st.cache_data(show_spinner="📧 Buscando boletos no Gmail...")
def carregar_dados():
    dados = buscar_e_extrair()
    if not dados:
        return pd.DataFrame(columns=["mes", "item", "valor"])
    df = pd.DataFrame(dados)
    df = df[df["item"].str.len() < 100]
    df = df[~df["item"].str.match(r'^[\d\s/R$]+$')]
    return df

# Exibir usuário logado na sidebar
user = st.session_state.get("user", {})
with st.sidebar:
    if user.get("picture"):
        try:
            import requests as _req, base64
            img_bytes = _req.get(user["picture"], timeout=5).content
            img_b64 = base64.b64encode(img_bytes).decode()
            st.markdown(
                f'<div style="text-align:center;margin-bottom:8px">'
                f'<img src="data:image/jpeg;base64,{img_b64}" width="72" style="border-radius:50%"/>'
                f'</div>',
                unsafe_allow_html=True
            )
        except:
            pass
    st.markdown(f'<div style="text-align:center"><b>{user.get("name", "Usuário")}</b></div>', unsafe_allow_html=True)
    st.markdown(f'<div style="text-align:center"><small>{user.get("email", "")}</small></div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚪 Sair", use_container_width=True):
        logout()
    if st.button("🔄 Atualizar dados", use_container_width=True):
        carregar_dados.clear()
        st.rerun()
    st.divider()

st.title("🏢 Dashboard Financeiro do Condomínio")

df = carregar_dados()
df = df.sort_values("mes")

meses = sorted(df["mes"].unique())

# Formatar mês de YYYY_MM para MM/YYYY
def formatar_mes(mes):
    try:
        partes = str(mes).replace("-", "_").split("_")
        return f"{partes[1]}/{partes[0]}"
    except:
        return mes

# ==========================
# DEFINIÇÃO DE ITENS FIXOS
# ==========================
ITENS_FIXOS = [
    "Taxa Fundo de Reserva",
    "Energia Elétrica",
    "Elevador",
    "Taxa de Cobrança CREA",
    "Limpeza e Conservação",
    "Limpeza Jardim /Calçada",
    "Limpeza Jardim",
    "Administração/Síndico",
    "Tarifa Bancária",
    "Taxa Básica Corsan"
]

# Filtrar itens fixos que podem ter variações no nome (como Consumo Água)
def e_item_fixo(item):
    if item in ITENS_FIXOS:
        return True
    # Consumo de água pode vir com informações adicionais
    if "Consumo Agua" in item or "Consumo Água" in item:
        return True
    return False

# ==========================
# FILTROS
# ==========================
st.sidebar.header("Filtros")

mes_atual = st.sidebar.selectbox("Mês Atual", meses, index=len(meses)-1, format_func=formatar_mes)
mes_anterior = st.sidebar.selectbox("Mês Comparação", meses, index=len(meses)-2, format_func=formatar_mes)


# ==========================
# PREPARAÇÃO (APENAS FIXOS)
# ==========================
df_atual = df[(df["mes"] == mes_atual) & (df["item"].apply(e_item_fixo))].copy()
df_ant = df[(df["mes"] == mes_anterior) & (df["item"].apply(e_item_fixo))].copy()

# Normalizar o nome do consumo de água para facilitar a comparação
def normalizar_consumo_agua(item):
    if "Consumo Agua" in item or "Consumo Água" in item:
        return "Consumo Água"
    return item

df_atual["item"] = df_atual["item"].apply(normalizar_consumo_agua)
df_ant["item"] = df_ant["item"].apply(normalizar_consumo_agua)

comparacao = df_atual.merge(
    df_ant,
    on="item",
    suffixes=("_atual", "_anterior"),
    how="outer"
).fillna(0)

comparacao["diferenca"] = comparacao["valor_atual"] - comparacao["valor_anterior"]

comparacao["percentual"] = comparacao.apply(
    lambda row: (
        (row["diferenca"] / row["valor_anterior"] * 100)
        if row["valor_anterior"] != 0 
        else (999.99 if row["valor_atual"] > 0 else 0)  # Indica novo item se antes era 0
    ),
    axis=1
)

# ==========================
# KPIs (TOTAL GERAL)
# ==========================
total_atual = df[df["mes"] == mes_atual]["valor"].sum()
total_anterior = df[df["mes"] == mes_anterior]["valor"].sum()

variacao_total = total_atual - total_anterior
percentual_total = (
    (variacao_total / total_anterior) * 100
    if total_anterior != 0 else 0
)

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
# TOP AUMENTOS (FIXOS)
# ==========================
st.subheader("📊 Top 5 Maiores Aumentos (Itens Fixos)")

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
    color_continuous_scale="Reds",
    custom_data=["percentual"]
)

fig1.update_layout(
    yaxis_title="",
    xaxis_title="Aumento (R$)",
    height=400
)

fig1.update_traces(
    texttemplate="R$ %{text:.2f}",
    hovertemplate='<b>%{y}</b><br>R$ %{x:,.2f}<br>%{customdata[0]:.2f}%<extra></extra>'
)

st.plotly_chart(fig1, use_container_width=True)

# ==========================
# REDUÇÕES
# ==========================
st.subheader("📉 Itens Fixos que Reduziram")

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
    color_continuous_scale="Greens",
    custom_data=["percentual"]
)

fig2.update_layout(
    yaxis_title="",
    xaxis_title="Redução (R$)",
    height=400
)

fig2.update_traces(
    texttemplate="R$ %{text:.2f}",
    hovertemplate='<b>%{y}</b><br>R$ %{x:,.2f}<br>%{customdata[0]:.2f}%<extra></extra>'
)

st.plotly_chart(fig2, use_container_width=True)

# ==========================
# TABELA COMPARATIVA FIXOS
# ==========================
st.subheader("📋 Tabela Comparativa Completa (Itens Fixos)")

# Ordenar por diferença (maiores aumentos primeiro)
comparacao_ordenada = comparacao.sort_values("diferenca", ascending=False)

# Formatar tabela com estilo
comparacao_formatada = comparacao_ordenada.copy()
comparacao_formatada["valor_anterior"] = comparacao_formatada["valor_anterior"].apply(lambda x: f"R$ {x:,.2f}")
comparacao_formatada["valor_atual"] = comparacao_formatada["valor_atual"].apply(lambda x: f"R$ {x:,.2f}")
comparacao_formatada["diferenca"] = comparacao_formatada["diferenca"].apply(lambda x: f"R$ {x:,.2f}")

# Adicionar setas SVG coloridas no percentual
def formatar_percentual(row):
    pct = row["percentual"]
    seta_up   = '<svg width="12" height="12" viewBox="0 0 10 10"><polygon points="5,0 10,10 0,10" fill="#ff4444"/></svg>'
    seta_down = '<svg width="12" height="12" viewBox="0 0 10 10"><polygon points="0,0 10,0 5,10" fill="#00cc44"/></svg>'
    if pct >= 999:
        return "🆕 Novo"
    elif pct > 0:
        return f'{seta_up} <span style="color:#ff4444">{pct:.2f}%</span>'
    elif pct < 0:
        return f'{seta_down} <span style="color:#00cc44">{abs(pct):.2f}%</span>'
    else:
        return "0.00%"

comparacao_formatada["percentual"] = comparacao_ordenada.apply(formatar_percentual, axis=1)

# Renomear colunas com os meses
col_anterior = formatar_mes(mes_anterior)
col_atual = formatar_mes(mes_atual)

comparacao_formatada = comparacao_formatada.rename(columns={
    "valor_anterior": col_anterior,
    "valor_atual": col_atual,
    "diferenca": "Diferença",
    "percentual": "Variação"
})

colunas = ["item", col_anterior, col_atual, "Diferença", "Variação"]
html_tabela = comparacao_formatada[colunas].to_html(escape=False, index=False)

st.markdown("""
<style>
.tabela-fixos { width: 100%; border-collapse: collapse; font-size: 14px; }
.tabela-fixos thead tr th { background-color: #1e1e2e; color: #cdd6f4; padding: 10px; text-align: left; border-bottom: 2px solid #444; }
.tabela-fixos tbody tr td { padding: 8px 10px; border-bottom: 1px solid #333; color: #cdd6f4; }
.tabela-fixos tbody tr:hover td { background-color: #2a2a3e; }
</style>
""", unsafe_allow_html=True)

st.markdown(html_tabela.replace('<table', '<table class="tabela-fixos"'), unsafe_allow_html=True)

# ==========================
# ITENS VARIÁVEIS
# ==========================
st.subheader("📌 Itens Variáveis do Mês Atual")

variaveis_atual = df[
    (df["mes"] == mes_atual) &
    (~df["item"].apply(e_item_fixo))
].copy()

variaveis_ant = df[
    (df["mes"] == mes_anterior) &
    (~df["item"].apply(e_item_fixo))
].copy()

# Normalizar nome removendo padrão de parcelas (ex: "2/2", "04/06", "3/3")
import re
def normalizar_parcela(item):
    return re.sub(r'\s*\d+/\d+\s*$', '', item).strip()

variaveis_atual["item_norm"] = variaveis_atual["item"].apply(normalizar_parcela)
variaveis_ant["item_norm"]   = variaveis_ant["item"].apply(normalizar_parcela)

# Separar itens cuja base existe no mês anterior
itens_anteriores_norm = set(variaveis_ant["item_norm"].unique())

variaveis_comparar = variaveis_atual[variaveis_atual["item_norm"].isin(itens_anteriores_norm)].copy()
variaveis_novos    = variaveis_atual[~variaveis_atual["item_norm"].isin(itens_anteriores_norm)].copy()

# --- Tabela comparativa (itens que existem nos dois meses) ---
if not variaveis_comparar.empty:
    st.markdown("**🔄 Itens que também ocorreram no mês anterior:**")

    # Merge pelo nome normalizado
    comp_var = variaveis_comparar.merge(
        variaveis_ant[["item_norm", "item", "valor"]].rename(columns={"item": "item_anterior"}),
        on="item_norm",
        suffixes=("_atual", "_anterior")
    )
    comp_var = comp_var.rename(columns={"valor_atual": "valor_atual", "valor_anterior": "valor_anterior"})
    comp_var["diferenca"] = comp_var["valor_atual"] - comp_var["valor_anterior"]
    comp_var["percentual"] = comp_var.apply(
        lambda row: (row["diferenca"] / row["valor_anterior"] * 100)
        if row["valor_anterior"] != 0 else 0,
        axis=1
    )
    comp_var = comp_var.sort_values("diferenca", ascending=False)

    seta_up   = '<svg width="12" height="12" viewBox="0 0 10 10"><polygon points="5,0 10,10 0,10" fill="#ff4444"/></svg>'
    seta_down = '<svg width="12" height="12" viewBox="0 0 10 10"><polygon points="0,0 10,0 5,10" fill="#00cc44"/></svg>'

    def formatar_pct_var(row):
        pct = row["percentual"]
        if pct > 0:
            return f'{seta_up} <span style="color:#ff4444">{pct:.2f}%</span>'
        elif pct < 0:
            return f'{seta_down} <span style="color:#00cc44">{abs(pct):.2f}%</span>'
        else:
            return "0.00%"

    comp_var_fmt = comp_var.copy()
    comp_var_fmt["valor_anterior"] = comp_var_fmt["valor_anterior"].apply(lambda x: f"R$ {x:,.2f}")
    comp_var_fmt["valor_atual"]    = comp_var_fmt["valor_atual"].apply(lambda x: f"R$ {x:,.2f}")
    comp_var_fmt["diferenca"]      = comp_var_fmt["diferenca"].apply(lambda x: f"R$ {x:,.2f}")
    comp_var_fmt["percentual"]     = comp_var.apply(formatar_pct_var, axis=1)

    comp_var_fmt = comp_var_fmt.rename(columns={
        "valor_anterior": col_anterior,
        "valor_atual":    col_atual,
        "diferenca":      "Diferença",
        "percentual":     "Variação"
    })

    html_var = comp_var_fmt[["item", col_anterior, col_atual, "Diferença", "Variação"]].to_html(escape=False, index=False)
    st.markdown(html_var.replace('<table', '<table class="tabela-fixos"'), unsafe_allow_html=True)

# --- Itens novos (sem comparação) ---
if not variaveis_novos.empty:
    st.markdown("**🆕 Itens que ocorreram apenas neste mês:**")
    variaveis_novos_fmt = variaveis_novos.copy()
    variaveis_novos_fmt["valor"] = variaveis_novos_fmt["valor"].apply(lambda x: f"R$ {x:,.2f}")
    variaveis_novos_fmt["Observação"] = "Sem ocorrência no mês anterior"
    st.dataframe(
        variaveis_novos_fmt[["item", "valor", "Observação"]],
        use_container_width=True,
        hide_index=True
    )

st.divider()

# ==========================
# GRÁFICO PIZZA
# ==========================
st.subheader("🥧 Composição do Mês Atual")

df_atual_completo = df[df["mes"] == mes_atual].copy()

# Agrupar itens pequenos em "Outros"
total = df_atual_completo["valor"].sum()
limite_percentual = 3  # Itens menores que 3% vão para "Outros"

df_atual_completo["percentual_total"] = (df_atual_completo["valor"] / total) * 100

# Separar itens grandes e pequenos
itens_grandes = df_atual_completo[df_atual_completo["percentual_total"] >= limite_percentual]
itens_pequenos = df_atual_completo[df_atual_completo["percentual_total"] < limite_percentual]

# Criar dataframe para o gráfico
if not itens_pequenos.empty:
    outros_valor = itens_pequenos["valor"].sum()
    df_pizza = pd.concat([
        itens_grandes[["item", "valor"]],
        pd.DataFrame([{"item": "Outros", "valor": outros_valor}])
    ])
else:
    df_pizza = itens_grandes[["item", "valor"]]

fig_pizza = px.pie(
    df_pizza,
    names="item",
    values="valor",
    title="Distribuição das Despesas (itens < 3% agrupados em 'Outros')"
)

fig_pizza.update_traces(
    textposition='inside', 
    textinfo='percent+label',
    hovertemplate='<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>'
)

fig_pizza.update_layout(
    height=600
)

st.plotly_chart(fig_pizza, use_container_width=True)

# ==========================
# EVOLUÇÃO TOTAL
# ==========================
st.subheader("📈 Evolução Total Mensal")

total_mes = df.groupby("mes")["valor"].sum().reset_index()
total_mes["mes_fmt"] = total_mes["mes"].apply(formatar_mes)

# Calcular variação percentual em relação ao mês anterior
total_mes["variacao_pct"] = total_mes["valor"].pct_change() * 100

fig3 = px.line(
    total_mes,
    x="mes_fmt",
    y="valor",
    markers=True,
    title="Evolução do Total Mensal",
    custom_data=["variacao_pct"]
)

fig3.update_traces(
    line_color='#1f77b4',
    line_width=3,
    marker=dict(size=10),
    hovertemplate='<b>%{x}</b><br>R$ %{y:,.2f}<br>%{customdata[0]:+.2f}%<extra></extra>'
)

fig3.update_layout(
    yaxis_title="Total (R$)",
    xaxis_title="",
    hovermode='x unified'
)

st.plotly_chart(fig3, use_container_width=True)

st.divider()

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

    for _, row in comparacao.iterrows():
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
