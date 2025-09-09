import os
import tweepy
import random
import schedule
import time
import requests

# ==============================
# Configurações via variáveis de ambiente
# ==============================
API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
ACCESS_SECRET = os.environ.get("ACCESS_SECRET")
AFILIADO = os.environ.get("AFILIADO")  # Ex: "af_id=SEU_CODIGO"

# Autenticação na API v2 do X
client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)

# API v1.1 só para upload de mídia e trends
auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
api_v1 = tweepy.API(auth)

# ==============================
# Categorias via API Shopee
# ==============================
CATEGORIAS_API = {
    "flash_sale": "https://shopee.com.br/api/v4/flash_sale/flash_sale_get_items?limit=20&offset=0",
    "eletronicos": "https://shopee.com.br/api/v4/search/search_items?by=pop&limit=20&match_id=11001048&newest=0&order=desc&page_type=search&scenario=PAGE_CATEGORY",
    "moda": "https://shopee.com.br/api/v4/search/search_items?by=pop&limit=20&match_id=11035647&newest=0&order=desc&page_type=search&scenario=PAGE_CATEGORY",
    "casa": "https://shopee.com.br/api/v4/search/search_items?by=pop&limit=20&match_id=11035652&newest=0&order=desc&page_type=search&scenario=PAGE_CATEGORY",
    "adulto": "https://shopee.com.br/api/v4/search/search_items?by=pop&limit=20&match_id=11044421&newest=0&order=desc&page_type=search&scenario=PAGE_CATEGORY"
}

# ==============================
# Buscar promoções da Shopee
# ==============================
def buscar_promocoes():
    url = random.choice(list(CATEGORIAS_API.values()))
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = r.json()

        promocoes = []
        if "items" in data:  # categorias normais
            items = data["items"]
            for item in items:
                produto = item["item_basic"]
                promocoes.append({
                    "titulo": produto["name"],
                    "link": f"https://shopee.com.br/product/{produto['shopid']}/{produto['itemid']}",
                    "img": f"https://cf.shopee.com.br/file/{produto['image']}"
                })
        elif "data" in data:  # flash sale
            items = data["data"]["items"]
            for item in items:
                produto = item["item"]
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
# Buscar hashtags em alta no X
# ==============================
def get_trend_hashtag():
    try:
        # 1 = mundial, 23424768 = Brasil (pode trocar WOEID)
        trends = api_v1.get_place_trends(23424768)
        hashtags = [t["name"] for t in trends[0]["trends"] if t["name"].startswith("#")]
        if hashtags:
            return random.choice(hashtags)
    except Exception as e:
        print("⚠️ Erro ao buscar trends:", e)
    return "#Shopee"

# ==============================
# Postar promoção
# ==============================
def postar_promocao():
    promocoes = buscar_promocoes()
    if not promocoes:
        print("Nenhuma promoção encontrada")
        return

    promo = random.choice(promocoes)
    hashtag = get_trend_hashtag()
    link_afiliado = f"{promo['link']}?{AFILIADO}"

    tweet = f"🔥 Promoção Shopee!\n{promo['titulo']}\n👉 {link_afiliado}\n{hashtag}"

    try:
        # baixar imagem
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
            print("✅ Tweet postado (sem imagem):", tweet)
    except Exception as e:
        print("⚠️ Erro ao postar:", e)

# ==============================
# Agenda: posta a cada 2h
# ==============================
schedule.every(2).minutes.do(postar_promocao)

print("🤖 Bot Shopee iniciado...")

while True:
    schedule.run_pending()
    time.sleep(60)
