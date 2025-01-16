import requests

def get_btc_price():
    url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
    try:
        response = requests.get(url, timeout=5)  # Timeout para evitar travar
        response.raise_for_status()  # Verifica se a resposta foi bem-sucedida (200 OK)
        data = response.json()
        return float(data["price"])
    except requests.exceptions.RequestException as e:
        print(f"Erro ao obter o preço do BTC: {e}")
        return None

# Testando a função
price = get_btc_price()
if price:
    print("Preço atual do BTC:", price)
else:
    print("Não foi possível obter o preço do BTC.")
