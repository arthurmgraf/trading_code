import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import requests
import numpy as np
import matplotlib
matplotlib.use("TkAgg")  # Configura backend interativo

# Configurar o estilo do Matplotlib
plt.style.use("dark_background")  # Fundo escuro

# Função para obter o preço atual do BTC
def get_btc_price():
    url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        return float(data["price"])
    except requests.exceptions.RequestException as e:
        print(f"Erro ao obter o preço do BTC: {e}")
        return None

# Função para processar os dados de liquidações
def process_liquidation_data(file):
    df = pd.read_csv(file)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["original_quantity"] = pd.to_numeric(df["original_quantity"], errors="coerce")
    
    # Agrupar por faixas de preço (bins)
    df["price_bin"] = pd.cut(df["price"], bins=np.arange(90000, 105000, 500))  # Ajuste o range conforme necessário
    heatmap_data = df.groupby("price_bin")["original_quantity"].sum().reset_index()
    heatmap_data["price_bin_center"] = heatmap_data["price_bin"].apply(lambda x: (x.left + x.right) / 2)
    return heatmap_data

# Função para atualizar o gráfico
def update(frame):
    current_price = get_btc_price()  # Obter o preço atual do BTC
    heatmap_data = process_liquidation_data("binance_BTC.csv")  # Processar dados de liquidações

    # Limpar o gráfico
    ax.clear()

    # Plotar barras horizontais coloridas representando o volume de liquidações
    for _, row in heatmap_data.iterrows():
        color = plt.cm.viridis(row["original_quantity"] / max(heatmap_data["original_quantity"]))  # Cor dinâmica
        ax.barh(row["price_bin_center"], width=row["original_quantity"], height=400, color=color, edgecolor="none")

    # Adicionar a linha horizontal representando o preço atual do BTC
    ax.axhline(current_price, color="yellow", linestyle="--", linewidth=2, label="Preço Atual BTC")

    # Configurações do gráfico
    ax.set_title("Heatmap de Liquidações BTC", fontsize=16, color="white")
    ax.set_xlabel("Volume de Liquidações", fontsize=12, color="white")
    ax.set_ylabel("Preço (USDT)", fontsize=12, color="white")
    ax.tick_params(axis="x", colors="white")
    ax.tick_params(axis="y", colors="white")
    ax.legend(facecolor="black", fontsize=10)

    # Adicionar barra de cores
    sm = plt.cm.ScalarMappable(cmap="viridis", norm=plt.Normalize(vmin=0, vmax=max(heatmap_data["original_quantity"])))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax)
    cbar.set_label("Volume de Liquidações", color="white", fontsize=12)
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")

# Configuração inicial do gráfico
fig, ax = plt.subplots(figsize=(12, 8))  # Tamanho do gráfico

# Armazenar a animação em uma variável global
global ani
ani = animation.FuncAnimation(fig, update, interval=5000, cache_frame_data=False)

# Exibir o gráfico
plt.show()
