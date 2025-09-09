import os
import tweepy
import requests
import random
import schedule
import time

API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
ACCESS_SECRET = os.environ.get("ACCESS_SECRET")
AFILIADO = os.environ.get("AFILIADO")  # Ex: "af_id=SEU_CODIGO"

auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)

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
        api.update_status(tweet)
        print("✅ Tweet postado:", tweet)
    except Exception as e:
        print("⚠️ Erro ao postar:", e)

schedule.every(2).minutes.do(postar_promocao)

print("🤖 Bot Shopee iniciado...")

while True:
    schedule.run_pending()
    time.sleep(60)
