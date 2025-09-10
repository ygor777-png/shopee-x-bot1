import os
import tweepy
import random
import schedule
import time
import requests
import json

# ==============================
# Configurações do Twitter (X)
# ==============================
API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
ACCESS_SECRET = os.environ.get("ACCESS_SECRET")
AFILIADO = os.environ.get("AFILIADO")  # Ex: af_id=SEUCODIGO
DEBUG = os.environ.get("DEBUG", "False").lower() == "true"

if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET, AFILIADO]):
    raise ValueError("⚠️ Variáveis de ambiente não configuradas corretamente.")

client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)

auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
api_v1 = tweepy.API(auth)

# ==============================
# Cabeçalhos e cache
# ==============================
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://shopee.com.br/",
    "x-api-source": "pc"
}

CACHE = set()

# ==============================
# Funções auxiliares
# ==============================
def gerar_titulo_criativo(nome_produto):
    ideias = [
        f"Você precisa disso: {nome_produto} 😍",
        f"Achado Shopee: {nome_produto} com preço top!",
        f"Não dá pra ignorar: {nome_produto} em oferta 🔥",
        f"Seu próximo favorito: {nome_produto} 🛒",
        f"Promoção que vale a pena: {nome_produto} 💸",
        f"Tá bombando: {nome_produto} com desconto!"
    ]
    return random.choice(ideias)

def get_top_hashtags():
    try:
        trends = api_v1.get_place_trends(23424768)  # Brasil
        hashtags = [t["name"] for t in trends[0]["trends"] if t["name"].startswith("#")]
        return hashtags[:3] if hashtags else ["#Shopee"]
    except Exception as e:
        print("⚠️ Erro trends:", e)
        return ["#Shopee"]

# ==============================
# Busca de produtos da Flash Sale
# ==============================
def buscar_flash_sale():
    promotion_id = "175588157636612"
    url = f"https://shopee.com.br/api/v4/flash_sale/get_all_itemids?promotionid={promotion_id}"

    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        item_ids = data.get("data", {}).get("item_brief_list", [])

        if not item_ids:
            print("⚠️ Nenhum item encontrado na Flash Sale.")
            return []

        produtos = []
        for item in item_ids:
            itemid = item.get("itemid")
            shopid = item.get("shopid")
            if not itemid or not shopid or itemid in CACHE:
                continue

            CACHE.add(itemid)

            # Buscar detalhes do produto
            detail_url = f"https://shopee.com.br/api/v4/item/get?itemid={itemid}&shopid={shopid}"
            r2 = requests.get(detail_url, headers=HEADERS, timeout=10)
            detail = r2.json().get("data")

            if detail:
                nome = detail.get("name")
                imagem = detail.get("image")
                preco = detail.get("price") / 100000
                preco_antigo = detail.get("price_before_discount", 0) / 100000

                if preco_antigo > preco:
                    produtos.append({
                        "titulo": nome,
                        "link": f"https://shopee.com.br/product/{shopid}/{itemid}",
                        "img": f"https://cf.shopee.com.br/file/{imagem}",
                        "preco": preco,
                        "preco_antigo": preco_antigo
                    })

        return produtos

    except Exception as e:
        print("⚠️ Erro ao buscar Flash Sale:", e)
        return []

# ==============================
# Postagem no X
# ==============================
def postar_promocao():
    promocoes = buscar_flash_sale()
    if not promocoes:
        return

    promo = random.choice(promocoes)
    link_afiliado = f"{promo['link']}?{AFILIADO}"
    hashtags = get_top_hashtags()
    titulo = gerar_titulo_criativo(promo["titulo"])

    tweet = (
        f"{titulo}\n"
        f"De R${promo['preco_antigo']:.2f} por R${promo['preco']:.2f} 🔥\n"
        f"👉 {link_afiliado}\n"
        f"{' '.join(hashtags)}"
    )

    if DEBUG:
        print("🧪 Modo DEBUG ativado. Tweet simulado:")
        print(tweet)
        return

    try:
        img_path = "temp.jpg"
        r = requests.get(promo["img"], stream=True, timeout=10)
        if r.status_code == 200:
            with open(img_path, "wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)

            media = api_v1.media_upload(img_path)
            client.create_tweet(text=tweet, media_ids=[media.media_id])
            print("✅ Tweet postado com imagem.")
            os.remove(img_path)
        else:
            client.create_tweet(text=tweet)
            print("✅ Tweet postado sem imagem.")
    except Exception as e:
        print("⚠️ Erro ao postar:", e)

# ==============================
# Agenda automática
# ==============================
schedule.every(1).minutes.do(postar_promocao)

print("🤖 Bot Shopee Flash Sale iniciado...")

while True:
    schedule.run_pending()
    time.sleep(60)
