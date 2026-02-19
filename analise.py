import pandas as pd

df = pd.read_csv("dados_condominio.csv")

# Ordena meses
df = df.sort_values("mes")

# Últimos dois meses
meses = sorted(df["mes"].unique())

if len(meses) < 2:
    print("Precisa de pelo menos 2 meses.")
    exit()

mes_atual = meses[-1]
mes_anterior = meses[-2]

print(f"\nComparando {mes_atual} vs {mes_anterior}\n")

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

comparacao = comparacao.sort_values("diferenca", ascending=False)

print(comparacao[["item", "valor_anterior", "valor_atual", "diferenca", "percentual"]])
