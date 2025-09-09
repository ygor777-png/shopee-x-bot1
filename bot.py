import os
import tweepy
import random
import schedule
import time

# ==============================
# Configurações via variáveis de ambiente
# ==============================
API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
ACCESS_SECRET = os.environ.get("ACCESS_SECRET")
AFILIADO = os.environ.get("AFILIADO")  # Ex: "af_id=SEU_CODIGO"

# Autenticação na API v2 do X (Twitter)
client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)

# ==============================
# Lista de promoções exemplo
# ==============================
promocoes = [
    {"titulo": "Fone Bluetooth 🔊", "link": "https://shope.ee/abcd123"},
    {"titulo": "Tênis esportivo 👟", "link": "https://shope.ee/wxyz456"},
    {"titulo": "Smartwatch ⌚", "link": "https://shope.ee/zyx987"}
]

def postar_promocao():
    promo = random.choice(promocoes)
    link_afiliado = f"{promo['link']}?{AFILIADO}"
    tweet = f"🔥 Promoção Shopee!\n{promo['titulo']}\n👉 {link_afiliado}"

    try:
        client.create_tweet(text=tweet)
        print("✅ Tweet postado:", tweet)
    except Exception as e:
        print("⚠️ Erro ao postar:", e)

# ==============================
# Agenda: posta 1x a cada 2 horas
# ==============================
schedule.every(20).hours.do(postar_promocao)

print("🤖 Bot Shopee iniciado...")

while True:
    schedule.run_pending()
    time.sleep(60)
