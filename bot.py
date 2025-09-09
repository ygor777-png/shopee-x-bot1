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

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

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
# Palavras-chave para busca na Shopee
# ==============================
PALAVRAS_CHAVE = [
    "oferta",
    "promoção",
    "eletrônicos",
    "moda masculina",
    "sapatos",
    "eletrodomésticos",
    "casa",
    "esporte",
]

# ==============================
# Função para buscar promoções via API JSON
# ==============================
def buscar_promocoes():
    termo = random.choice(PALAVRAS_CHAVE)
    url = "https://shopee.com.br/api/v4/search/search_items"
    params = {
        "by": "relevancy",
        "keyword": termo,
        "limit": 20,
        "newest": 0,
        "order": "desc",
        "page_type": "search"
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code != 200:
            print("⚠️ Erro na API Shopee:", r.status_code)
            return []

        data = r.json()
        promocoes = []
        for item in data.get("items", []):
            produto = item.get("item_basic", {})
            nome = produto.get("name")
            preco = produto.get("price") / 100000  # preço vem multiplicado
            imagem = f"https://cf.shopee.com.br/file/{produto.get('image')}"
            link = f"https://shopee.com.br/product/{produto.get('shopid')}/{produto.get('itemid')}"
            promocoes.append({
                "titulo": nome,
                "preco": preco,
                "link": link,
                "img": imagem
            })
        return promocoes
    except Exception as e:
        print("⚠️ Erro ao buscar promoções:", e)
        return []

# ==============================
# Função para reescrever título com IA
# ==============================
def melhorar_titulo(titulo):
    if not OPENAI_API_KEY:
        return titulo

    try:
        import openai
        openai.api_key = OPENAI_API_KEY
        prompt = f"Reescreva este título de produto de forma divertida, curta e chamativa para redes sociais: {titulo}"
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=30,
            temperature=0.8
        )
        return response.choices[0].text.strip()
    except Exception as e:
        print("⚠️ Erro na IA:", e)
        return titulo

# ==============================
# Função para postar promoção no X
# ==============================
def postar_promocao():
    promocoes = buscar_promocoes()
    if not promocoes:
        print("Nenhuma promoção encontrada")
        return

    promo = random.choice(promocoes)
    titulo = melhorar_titulo(promo['titulo'])
    link_afiliado = f"{promo['link']}?{AFILIADO}"
    tweet = f"🔥 Promoção Shopee!\n{titulo}\n💰 R${promo['preco']:.2f}\n👉 {link_afiliado}"

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
            print("✅ Tweet postado (sem imagem):", tweet)
    except Exception as e:
        print("⚠️ Erro ao postar:", e)

# ==============================
# Agenda: posta 1x a cada 2 horas
# ==============================
schedule.every(2).hours.do(postar_promocao)

print("🤖 Bot Shopee iniciado...")

while True:
    schedule.run_pending()
    time.sleep(60)
