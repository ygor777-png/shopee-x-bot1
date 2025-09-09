import os
import tweepy
import random
import schedule
import time
import requests

# ==============================
# Configurações do Twitter (X)
# ==============================
API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
ACCESS_SECRET = os.environ.get("ACCESS_SECRET")
AFILIADO = os.environ.get("AFILIADO")  # Ex: af_id=SEUCODIGO

client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)

auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
api_v1 = tweepy.API(auth)

# ==============================
# Busca na Shopee (pública via JSON)
# ==============================
CATEGORIAS = ["fone bluetooth", "tênis esportivo", "roupa feminina", "decoração casa", "sex shop"]

def buscar_promocoes():
    termo = random.choice(CATEGORIAS)
    url = f"https://shopee.com.br/api/v4/search/search_items?by=relevancy&keyword={termo}&limit=20&newest=0&order=desc&page_type=search"

    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        data = r.json()

        promocoes = []
        if "items" in data:
            for item in data["items"]:
                produto = item["item_basic"]
                promocoes.append({
                    "titulo": produto["name"],
                    "link": f"https://shopee.com.br/product/{produto['shopid']}/{produto['itemid']}",
                    "img": f"https://cf.shopee.com.br/file/{produto['image']}"
                })

        return promocoes
    except Exception as e:
        print("⚠️ Erro ao buscar promoções:", e)
        return []

# ==============================
# Hashtags de trends no X
# ==============================
def get_trend_hashtag():
    try:
        trends = api_v1.get_place_trends(23424768)  # Brasil
        hashtags = [t["name"] for t in trends[0]["trends"] if t["name"].startswith("#")]
        if hashtags:
            return random.choice(hashtags)
    except Exception as e:
        print("⚠️ Erro trends:", e)
    return "#Shopee"

# ==============================
# Postagem no X
# ==============================
def postar_promocao():
    promocoes = buscar_promocoes()
    if not promocoes:
        print("Nenhuma promoção encontrada")
        return

    promo = random.choice(promocoes)
    hashtag = get_trend_hashtag()
    link_afiliado = f"{promo['link']}?{AFILIADO}"

    tweet = f"🔥 Oferta Shopee!\n{promo['titulo']}\n👉 {link_afiliado}\n{hashtag}"

    try:
        img_path = "temp.jpg"
        r = requests.get(promo["img"], stream=True, timeout=10)
        if r.status_code == 200:
            with open(img_path, "wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)

            media = api_v1.media_upload(img_path)
            client.create_tweet(text=tweet, media_ids=[media.media_id])
            print("✅ Tweet postado com imagem:", tweet)
            os.remove(img_path)
        else:
            client.create_tweet(text=tweet)
            print("✅ Tweet postado sem imagem:", tweet)
    except Exception as e:
        print("⚠️ Erro ao postar:", e)

# ==============================
# Agenda: a cada 2h
# ==============================
schedule.every(1).minutes.do(postar_promocao)

print("🤖 Bot Shopee iniciado...")

while True:
    schedule.run_pending()
    time.sleep(60)
