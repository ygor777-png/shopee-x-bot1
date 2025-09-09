import os
import tweepy
import random
import schedule
import time
import requests
from bs4 import BeautifulSoup

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

auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
api_v1 = tweepy.API(auth)  # usado só para upload de mídia

# ==============================
# Função para buscar promoções na Shopee (scraping)
# ==============================
def buscar_promocoes():
    url = "https://shopee.com.br/flash_sale"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        promocoes = []
        # cada produto pode estar em tags <img> e <a>
        for item in soup.select("a"):
            link = item.get("href")
            titulo = item.get_text().strip()
            img_tag = item.find("img")
            img_link = img_tag["src"] if img_tag and "http" in img_tag["src"] else None

            if link and "shopee" in link and titulo and img_link:
                if not link.startswith("http"):
                    link = "https://shopee.com.br" + link
                promocoes.append({"titulo": titulo, "link": link, "img": img_link})
        return promocoes
    except Exception as e:
        print("⚠️ Erro ao buscar promoções:", e)
        return []

# ==============================
# Função para postar promoção no X
# ==============================
def postar_promocao():
    promocoes = buscar_promocoes()
    if not promocoes:
        print("Nenhuma promoção encontrada")
        return

    promo = random.choice(promocoes)
    link_afiliado = f"{promo['link']}?{AFILIADO}"
    tweet = f"🔥 Promoção Shopee!\n{promo['titulo']}\n👉 {link_afiliado}"

    try:
        # Baixar imagem
        img_path = "temp.jpg"
        r = requests.get(promo["img"], stream=True, timeout=10)
        if r.status_code == 200:
            with open(img_path, "wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)

            # Upload da imagem pela API v1.1
            media = api_v1.media_upload(img_path)

            # Postar tweet com imagem
            client.create_tweet(text=tweet, media_ids=[media.media_id])
            print("✅ Tweet postado com imagem:", tweet)
            os.remove(img_path)
        else:
            client.create_tweet(text=tweet)
            print("✅ Tweet postado (sem imagem):", tweet)
    except Exception as e:
        print("⚠️ Erro ao postar:", e)

# ==============================
# Agenda: posta 1x a cada 2 horas
# ==============================
schedule.every(2).minutes.do(postar_promocao)

print("🤖 Bot Shopee iniciado...")

while True:
    schedule.run_pending()
    time.sleep(60)
