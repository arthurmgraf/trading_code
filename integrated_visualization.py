import asyncio
import json
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import requests
import numpy as np
import matplotlib
from websockets import connect
import mplfinance as mpf
from datetime import datetime
from matplotlib.ticker import ScalarFormatter
import pytz
from tkinter import Tk, Button as TkButton
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

matplotlib.use("TkAgg")  # Configura backend interativo

# Configuração personalizada do estilo com fundo cinza escuro
plt.rcParams.update({
    "figure.facecolor": "#A9A9A9",  # Fundo da figura
    "axes.facecolor": "#A9A9A9",    # Fundo dos eixos
    "axes.edgecolor": "white",      # Cor das bordas dos eixos
    "axes.labelcolor": "white",     # Cor das legendas dos eixos
    "grid.color": "white",          # Cor da grade
    "grid.linestyle": "--",         # Estilo da grade
    "xtick.color": "white",         # Cor dos ticks do eixo X
    "ytick.color": "white",         # Cor dos ticks do eixo Y
    "text.color": "white",          # Cor do texto
    "axes.titlecolor": "white"      # Cor do título do gráfico
})

# Configurações gerais
websocket_uri = "wss://fstream.binance.com/ws/!forceOrder@arr"
filename = "binance_BTC.csv"  # Nome do arquivo para BTC
candlestick_data = []  # Lista para armazenar dados de candles

# Intervalo de tempo para o gráfico
interval = "5m"  # Intervalo padrão inicial
intervals = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1w"]

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

# Função para obter o histórico de preços do BTC
def get_btc_historical(interval="1m", limit=500):
    url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval={interval}&limit={limit}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume", 
            "close_time", "quote_asset_volume", "number_of_trades", 
            "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        
        # Convertendo para datetime e ajustando para o fuso horário de Brasília
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        brasilia_tz = pytz.timezone("America/Sao_Paulo")
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC").dt.tz_convert(brasilia_tz)
        
        # Selecionando colunas relevantes
        df = df[["timestamp", "open", "high", "low", "close", "volume"]]
        df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
        return df
    except requests.exceptions.RequestException as e:
        print(f"Erro ao obter o histórico de preços: {e}")
        return pd.DataFrame()

# Função para capturar liquidações e salvar no CSV
async def binance_liquidations(uri, filename):
    async with connect(uri) as websocket:  # Mantém o loop de conexão funcional
        try:
            while True:
                msg = await websocket.recv()  # Recebe a mensagem
                print(f"[WebSocket] Mensagem recebida: {msg}")  # Log da mensagem recebida
                data = json.loads(msg)  # Decodifica o JSON
                
                # Verifica se o símbolo é BTCUSDT
                if "o" in data and data["o"].get("s") == "BTCUSDT":
                    msg = data["o"]  # Extrai os dados relevantes
                    filtered_msg = [str(x) for x in msg.values()]  # Converte para strings
                    print(f"[WebSocket] Salvando no arquivo: {filtered_msg}")  # Log dos dados a serem salvos
                    # Salva no arquivo CSV
                    with open(filename, "a") as f:
                        f.write(",".join(filtered_msg) + "\n")
        except Exception as e:
            print(f"Erro: {e}")  # Exibe o erro no console
            await asyncio.sleep(5)  # Aguarda antes de tentar reconectar

# Certifique-se de que o arquivo CSV existe
if not os.path.isfile(filename):
    print(f"Arquivo {filename} não encontrado. Criando arquivo...")
    with open(filename, "w") as f:
        f.write(",".join(["symbol", "side", "order_type", "time_in_force",
                          "original_quantity", "price", "average_price",
                          "order_status", "order_last_filled_quantity",
                          "order_filled_accumalated_quantity",
                          "order_trade_time"]) + "\n")

# Função para processar os dados de liquidações
def process_liquidation_data(file):
    if not os.path.isfile(file) or os.stat(file).st_size == 0:
        print(f"Arquivo {file} não encontrado ou está vazio.")
        return pd.DataFrame(columns=["price", "original_quantity", "timestamp"])
    
    df = pd.read_csv(file)
    print(f"Dados carregados de {file}:", df.head())  # Log para validar o conteúdo do arquivo
    df.dropna(subset=["price", "original_quantity"], inplace=True)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["original_quantity"] = pd.to_numeric(df["original_quantity"], errors="coerce")
    df.dropna(inplace=True)

    # Subtraindo 20000000 de order_trade_time
    if "order_trade_time" in df.columns:
        df["order_trade_time"] = pd.to_numeric(df["order_trade_time"], errors="coerce") - 20000000
        df.dropna(subset=["order_trade_time"], inplace=True)
        # Convertendo order_trade_time para timestamp
        df["timestamp"] = pd.to_datetime(df["order_trade_time"], unit="ms")
    else:
        df["timestamp"] = None

    return df

# Função para alterar o intervalo
def change_interval(new_interval):
    global interval, candlestick_data
    interval = new_interval  # Atualiza o intervalo global
    candlestick_data = []  # Limpa os dados para recarregar
    print(f"Intervalo alterado para {interval}")
    update(None)  # Atualiza o gráfico imediatamente

# Função para atualizar os dados de candlesticks
def update_candlesticks():
    global candlestick_data
    brasilia_tz = pytz.timezone("America/Sao_Paulo")
    
    if len(candlestick_data) == 0:
        historical_data = get_btc_historical(interval=interval, limit=200)
        candlestick_data.extend(historical_data.to_dict("records"))
    
    current_price = get_btc_price()
    now = datetime.now().astimezone(brasilia_tz)  # Ajustando o horário atual para Brasília

    if not candlestick_data or current_price is None:
        print("Dados de candlesticks estão vazios ou preço atual é inválido. Ignorando atualização.")
        return pd.DataFrame()

    if pd.to_datetime(candlestick_data[-1]["timestamp"]).minute != now.minute:
        candlestick_data.append({
            "timestamp": now, 
            "open": current_price, 
            "high": current_price,
            "low": current_price, 
            "close": current_price, 
            "volume": 0
        })
    else:
        candlestick_data[-1]["close"] = current_price
        candlestick_data[-1]["high"] = max(candlestick_data[-1]["high"], current_price)
        candlestick_data[-1]["low"] = min(candlestick_data[-1]["low"], current_price)
    
    df = pd.DataFrame(candlestick_data)
    df.set_index("timestamp", inplace=True)
    return df

# Função para atualizar o gráfico
def update(frame):
    current_price = get_btc_price()
    liquidation_data = process_liquidation_data(filename)
    print(f"Dados processados para liquidações: {liquidation_data}")  # Log para verificar os dados processados
    candle_df = update_candlesticks()
    ax.clear()

    # Configuração de cores personalizadas para os candles
    custom_style = mpf.make_mpf_style(
        base_mpf_style='charles',  # Estilo base
        marketcolors=mpf.make_marketcolors(
            up='white',        # Cor dos candles de alta
            down='black',      # Cor dos candles de baixa
            edge='black',      # Cor do contorno do candle
            wick='black',      # Cor do pavio do candle
            volume='in',       # Volume usa as mesmas cores de alta e baixa
        )
    )

    # Plotando os candlesticks
    mpf.plot(
        candle_df.tail(500),  # Mostra apenas os últimos 500 candles
        type="candle", 
        ax=ax, 
        style=custom_style,  # Usa o estilo personalizado
        show_nontrading=True,
        warn_too_much_data=500
    )

    # Adicionando os pontos de liquidação
    if not liquidation_data.empty:
        liquidation_data["color"] = liquidation_data["original_quantity"].apply(lambda x: "yellow" if x > 0.1 else "green")
        ax.scatter(
            liquidation_data["timestamp"],
            liquidation_data["price"],
            c=liquidation_data["color"],
            s=50,  # Tamanho do ponto
            alpha=0.6
        )

    # Adicionando a linha do preço atual e a legenda que o acompanha
    if current_price is not None:
        ax.axhline(current_price, color="white", linestyle="--", linewidth=0.5)
        ax.annotate(
            f"{current_price:.2f}",  # Texto com o preço atual
            xy=(1, current_price),  # Posição no gráfico
            xycoords=("axes fraction", "data"),  # Coordenadas relativas ao gráfico
            xytext=(10, 0),  # Deslocamento do texto
            textcoords="offset points",
            fontsize=10,
            color="white",
            bbox=dict(boxstyle="round,pad=0.3", edgecolor="white", facecolor="#333333"),
        )

    # Configuração do restante do gráfico
    ax.set_title(f"BTCUSDT BINANCE ({interval})", fontsize=14, color="white", loc="left")
    # ax.set_xlabel("time", fontsize=12, color="white")
    ax.set_ylabel("Preço (USDT)", fontsize=12, color="white")
    ax.tick_params(axis="x", rotation=0, colors="white")
    ax.tick_params(axis="y", rotation=0, colors="white")

    # Configurar o eixo Y para exibir números completos
    ax.get_yaxis().set_major_formatter(ScalarFormatter())
    ax.get_yaxis().get_major_formatter().set_scientific(False)
    ax.get_yaxis().get_major_formatter().set_useOffset(False)

# Classe personalizada para a barra de ferramentas
class CustomToolbar(NavigationToolbar2Tk):
    def __init__(self, canvas, root, intervals, callback):
        super().__init__(canvas, root)

        # Adiciona botões extras para os intervalos
        for interval in intervals:
            btn = TkButton(
                master=root, text=interval, command=lambda intv=interval: callback(intv),
                bg="#333", fg="white", relief="ridge", padx=5, pady=2
            )
            btn.pack(side="left", padx=2, pady=2)

# Configuração inicial do gráfico com toolbar personalizada
def setup_graph_with_toolbar(fig, intervals, callback):
    root = Tk()  # Janela principal
    root.title("BTC Visualization with Toolbar")

    # Adiciona canvas à janela
    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

    # Adiciona toolbar personalizada
    toolbar = CustomToolbar(canvas, root, intervals, callback)
    toolbar.update()

    # Desenha o gráfico inicial
    canvas.draw()

    # Loop principal da interface gráfica
    root.mainloop()

# Configuração inicial do gráfico com interatividade
fig, ax = plt.subplots(figsize=(12, 8))

# Ajuste do layout
plt.subplots_adjust(left=0.05, bottom=0.1, right=0.918, top=0.95, wspace=0.2, hspace=0.2)

# Configuração da animação
ani = animation.FuncAnimation(fig, update, interval=5000, cache_frame_data=False)

# Configuração do loop assíncrono
loop = asyncio.get_event_loop()
loop.create_task(binance_liquidations(websocket_uri, filename))

# Substitui plt.show() para usar a interface com toolbar personalizada
setup_graph_with_toolbar(fig, intervals, change_interval)
