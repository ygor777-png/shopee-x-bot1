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
# Categorias e Emojis
# ==============================
CATEGORIAS = {
    "moda": 110443,
    "casa": 110444,
    "ofertas": 110445,
    "tecnologia": 110429,
    "adulto": 110451
}

EMOJIS = {
    "moda": "👗",
    "casa": "🏠",
    "ofertas": "💥",
    "tecnologia": "📱",
    "adulto": "🔞"
}

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

def extrair_promocoes(data, emoji):
    promocoes = []
    for item in data.get("items", []):
        produto = item.get("item_basic")
        if produto and produto.get("price_before_discount", 0) > produto.get("price", 0):
            itemid = produto["itemid"]
            if itemid in CACHE:
                continue
            CACHE.add(itemid)
            promocoes.append({
                "titulo": f"{emoji} {produto['name']}",
                "link": f"https://shopee.com.br/product/{produto['shopid']}/{itemid}",
                "img": f"https://cf.shopee.com.br/file/{produto['image']}"
            })
    return promocoes

# ==============================
# Busca por categoria com desconto
# ==============================
def buscar_promocoes():
    categoria_nome, categoria_id = random.choice(list(CATEGORIAS.items()))
    emoji = EMOJIS.get(categoria_nome, "🛍️")
    print(f"🔍 Buscando por categoria: {categoria_nome}")

    url = f"https://shopee.com.br/api/v4/search/search_items?by=pop&limit=20&match_id={categoria_id}&newest=0&order=desc&page_type=category"

    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        promocoes = extrair_promocoes(data, emoji)

        if not promocoes:
            print("⚠️ Nenhum item com desconto encontrado.")
        return promocoes

    except Exception as e:
        print("⚠️ Erro ao buscar promoções:", e)
        return []

# ==============================
# Postagem no X
# ==============================
def postar_promocao():
    promocoes = buscar_promocoes()
    if not promocoes:
        return

    promo = random.choice(promocoes)
    link_afiliado = f"{promo['link']}?{AFILIADO}"
    hashtags = get_top_hashtags()
    titulo = gerar_titulo_criativo(promo["titulo"])

    tweet = f"{titulo}\n👉 {link_afiliado}\n{' '.join(hashtags)}"

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

print("🤖 Bot Shopee iniciado...")

while True:
    schedule.run_pending()
    time.sleep(60)
