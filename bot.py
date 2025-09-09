import os
import tweepy
import random
import schedule
import time
import requests
from bs4 import BeautifulSoup

# Configurações (variáveis de ambiente)
API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
ACCESS_SECRET = os.environ.get("ACCESS_SECRET")
AFILIADO = os.environ.get("AFILIADO")

client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)

def buscar_promocoes():
    url = "https://shopee.com.br/flash_sale?promotionId=123456"  # Exemplo (ofertas relâmpago)
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")

    promocoes = []
    for item in soup.select("a"):  # simplificado
        link = item.get("href")
        titulo = item.get_text().strip()
        if link and "shopee" in link and titulo:
            promocoes.append({"titulo": titulo, "link": "https://shopee.com.br" + link})

    return promocoes

def postar_promocao():
    promocoes = buscar_promocoes()
    if not promocoes:
        print("Nenhuma promoção encontrada")
        return

    promo = random.choice(promocoes)
    link_afiliado = f"{promo['link']}?{AFILIADO}"
    tweet = f"🔥 Promoção Shopee!\n{promo['titulo']}\n👉 {link_afiliado}"

    try:
        client.create_tweet(text=tweet)
        print("✅ Tweet postado:", tweet)
    except Exception as e:
        print("⚠️ Erro ao postar:", e)

schedule.every(2).minutes.do(postar_promocao)

print("🤖 Bot Shopee iniciado...")

while True:
    schedule.run_pending()
    time.sleep(60)
