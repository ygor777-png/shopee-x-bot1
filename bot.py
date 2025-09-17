from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import os, re, random, requests, pytz, tweepy, pyshorteners
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

TOKEN = os.getenv("BOT_TOKEN")

# IDs dos grupos (substitua pelos reais)
GRUPO_ENTRADA_ID = -4653176769
GRUPO_SAIDA_ID = -1001592474533

# Timezone Brasil
TZ = pytz.timezone("America/Sao_Paulo")

# -------- Configuração do X (Twitter) --------
API_KEY = os.getenv("API_KEY")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")

auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET_KEY, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
twitter_api = tweepy.API(auth)

# -------- Funções utilitárias --------
def encurtar_link(link):
    """Encurta o link usando TinyURL."""
    try:
        s = pyshorteners.Shortener()
        return s.tinyurl.short(link)
    except:
        return link

def extrair_titulo(link):
    """Extrai o título cru da página (fallback simples)."""
    try:
        r = requests.get(link, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        meta_title = soup.find("meta", property="og:title")
        if meta_title and meta_title.get("content"):
            return meta_title["content"].strip()
        if soup.title:
            return soup.title.string.strip()
        return "Produto em Oferta"
    except:
        return "Produto em Oferta"

def gerar_titulo_criativo(titulo_original):
    """Transforma o título cru em algo mais chamativo + nome do produto."""
    prefixos = [
        "🔥 Oferta Imperdível:",
        "💥 Promoção Relâmpago:",
        "✨ Destaque do Dia:",
        "🎯 Achado Especial:",
        "🛒 Super Desconto:"
    ]
    prefixo = random.choice(prefixos)
    palavras = titulo_original.split()
    resumo = " ".join(palavras[:8])
    return f"{prefixo} {resumo}"

def gerar_texto_desconto(preco_anterior, preco_atual):
    """Gera frases variadas para destacar o desconto."""
    modelos = [
        f"💰 De: {preco_anterior}\n✅ Por: {preco_atual}",
        f"💸 Antes {preco_anterior}, agora só {preco_atual}!",
        f"🔥 De {preco_anterior} caiu para {preco_atual}!",
        f"🎉 De {preco_anterior} por apenas {preco_atual}!",
        f"⚡ Aproveite: {preco_anterior} ➝ {preco_atual}"
    ]
    return random.choice(modelos)

def criar_anuncio(link, titulo, preco_anterior, preco_atual):
    desconto = gerar_texto_desconto(preco_anterior, preco_atual)
    return f"""
{titulo}

{desconto}

👉 Garanta aqui: {link}
"""

# -------- Função para enviar anúncio --------
def enviar_anuncio(context):
    job = context.job
    anuncio = job.context["anuncio"]

    # Envia no grupo do Telegram
    context.bot.send_message(chat_id=job.context["chat_id"], text=anuncio)

    # Posta também no X
    try:
        texto_tweet = anuncio.replace("\n", " ")
        if len(texto_tweet) > 280:
            texto_tweet = texto_tweet[:277] + "..."
        twitter_api.update_status(texto_tweet)
    except Exception as e:
        print("Erro ao postar no X:", e)

# -------- Processamento da mensagem --------
def processar_mensagem(update, context):
    if not update.message or not update.message.text:
        return  

    if update.message.chat_id != GRUPO_ENTRADA_ID:
        return

    texto = update.message.text.strip()

    # Formato esperado: link preço_anterior preço_atual [HH:MM]
    match = re.match(r"(https?://\S+)\s+([\w\.,R\$]+)\s+([\w\.,R\$]+)(?:\s+(\d{1,2}:\d{2}))?", texto)
    if not match:
        update.message.reply_text("Formato inválido. Use: link preço_anterior preço_atual [HH:MM]")
        return

    link = match.group(1)
    preco_anterior = match.group(2)
    preco_atual = match.group(3)
    horario = match.group(4)

    # Encurta o link
    link_encurtado = encurtar_link(link)

    # Extrai título cru e gera criativo com nome do produto
    titulo_original = extrair_titulo(link)
    titulo = gerar_titulo_criativo(titulo_original)

    anuncio = criar_anuncio(link_encurtado, titulo, preco_anterior, preco_atual)

    if horario:
        try:
            agora = datetime.now(TZ)
            hora, minuto = map(int, horario.split(":"))
            agendamento = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
            if agendamento < agora:
                agendamento += timedelta(days=1)

            delay = (agendamento - agora).total_seconds()

            context.job_queue.run_once(
                enviar_anuncio,
                delay,
                context={"chat_id": GRUPO_SAIDA_ID, "anuncio": anuncio}
            )

            update.message.reply_text(f"✅ Link agendado para {agendamento.strftime('%H:%M')} com título: {titulo}")
        except Exception as e:
            update.message.reply_text(f"⚠️ Horário inválido. Use formato HH:MM. Erro: {e}")
    else:
        # Envia no Telegram
        context.bot.send_message(chat_id=GRUPO_SAIDA_ID, text=anuncio)
        # Posta também no X
        try:
            texto_tweet = anuncio.replace("\n", " ")
            if len(texto_tweet) > 280:
                texto_tweet = texto_tweet[:277] + "..."
            twitter_api.update_status(texto_tweet)
        except Exception as e:
            print("Erro ao postar no X:", e)

        update.message.reply_text(f"✅ Link enviado imediatamente com título: {titulo}")

def start(update, context):
    update.message.reply_text("Envie: link preço_anterior preço_atual [HH:MM] no grupo de entrada.")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, processar_mensagem))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
