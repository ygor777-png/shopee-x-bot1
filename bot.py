from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import os, re, random, pytz, tweepy, pyshorteners, urllib.parse
from datetime import datetime, timedelta

TOKEN = os.getenv("BOT_TOKEN")

# IDs dos grupos
GRUPO_ENTRADA_ID = -4653176769
GRUPO_SAIDA_ID = -1001592474533

# Seu user_id do Telegram (descubra com @userinfobot e coloque aqui)
ADMIN_ID = 1420827874  # <<< SUBSTITUA PELO SEU ID REAL

# Timezone Brasil
TZ = pytz.timezone("America/Sao_Paulo")

# -------- Configuração do X (Twitter) --------
API_KEY = os.getenv("API_KEY")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")

auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET_KEY, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
twitter_api = tweepy.API(auth)

# -------- Link centralizador --------
LINK_CENTRAL = "https://atom.bio/ofertas_express"

# -------- Funções utilitárias --------
def encurtar_link(link):
    try:
        s = pyshorteners.Shortener()
        return s.tinyurl.short(link)
    except:
        return link
def gerar_titulo_criativo(titulo_manual):
    prefixos = [
        "🔥 Oferta Imperdível:",
        "⚡ Promoção Relâmpago:",
        "✨ Destaque do Dia:",
        "🔍 Achado Especial:",
        "🛒 Super Desconto:",
        "🏆 Top Oferta:",
        "💎 Oferta Premium:",
        "🎯 Escolha Certa:",
        "🚀 Oferta Explosiva:",
        "🎁 Promoção Exclusiva:",
        "📢 Atenção:",
        "💥 Desconto Incrível:",
        "🌟 Super Achado:",
        "🏷️ Preço Baixou:",
        "📌 Oferta Limitada:",
        "⏳ Só Hoje:",
        "🥇 Campeão de Vendas:",
        "🔥 Queima de Estoque:",
        "💡 Oportunidade Única:",
        "🎉 Oferta Especial:",
        "📦 Estoque Limitado:",
        "🕒 Últimas Horas:",
        "⭐ Oferta 5 Estrelas:",
        "🎊 Promoção do Momento:"
    ]
    prefixo = random.choice(prefixos)
    return f"{prefixo} {titulo_manual}"

def gerar_texto_preco(precos):
    if len(precos) == 1:
        preco = precos[0]
        modelos_unico = [
            f"💰 Por: {preco}",
            f"🔥 Apenas {preco}!",
            f"🎯 Leve já por {preco}!",
            f"🛒 Disponível por {preco}",
            f"⚡ Oferta: {preco}",
            f"🏷️ Preço único: {preco}",
            f"🎉 Só hoje: {preco}",
            f"📌 Valor promocional: {preco}",
            f"✅ Agora por {preco}",
            f"🥳 Aproveite por {preco}!",
            f"💎 Exclusivo: {preco}",
            f"🚀 Pegue já por {preco}",
            f"🎁 Oferta especial: {preco}"
        ]
        return random.choice(modelos_unico)
    else:
        preco_anterior, preco_atual = precos
        modelos = [
            f"💰 De: {preco_anterior}\n✅ Por: {preco_atual}",
            f"💸 Antes {preco_anterior}, agora só {preco_atual}!",
            f"🔥 De {preco_anterior} caiu para {preco_atual}!",
            f"🎉 De {preco_anterior} por apenas {preco_atual}!",
            f"➡️ Aproveite: {preco_anterior} → {preco_atual}",
            f"⚡ Desconto relâmpago: {preco_anterior} baixou para {preco_atual}!",
            f"🏷️ Preço antigo: {preco_anterior}\n👉 Novo preço: {preco_atual}",
            f"📉 De {preco_anterior} despencou para {preco_atual}!",
            f"🥳 Promoção: {preco_anterior} virou {preco_atual}!",
            f"🤑 De {preco_anterior} por só {preco_atual}!",
            f"💎 De {preco_anterior} agora exclusivo por {preco_atual}!",
            f"🚀 Oferta turbo: {preco_anterior} → {preco_atual}",
            f"🎁 Antes {preco_anterior}, hoje {preco_atual}!",
            f"⭐ De {preco_anterior} baixou para {preco_atual}!"
        ]
        return random.choice(modelos)

def criar_anuncio(link, titulo, precos):
    texto_preco = gerar_texto_preco(precos)
    link_central_encurtado = encurtar_link(LINK_CENTRAL)

    return f"""{titulo}

{texto_preco}

👉 Compre por aqui: {link}

⚠️ Corre que acaba rapido!

🌐 Siga nossas redes sociais:
{link_central_encurtado}"""

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

        # Monta botão de compartilhamento
        url_tweet = "https://twitter.com/intent/tweet?text=" + urllib.parse.quote(texto_tweet)
        keyboard = [[InlineKeyboardButton("🐦 Compartilhar no X", url=url_tweet)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"⚠️ Não consegui postar no X.\nAqui está o texto pronto:\n\n{anuncio}",
            reply_markup=reply_markup
        )

def processar_mensagem(update, context):
    if not update.message or not update.message.text:
        return  

    if update.message.chat_id != GRUPO_ENTRADA_ID:
        return

    texto = update.message.text.strip()

    # Formato esperado: link "Título" preço [preço_atual] [HH:MM]
    match = re.match(r'(https?://\S+)\s+"([^"]+)"\s+([\w\.,R\$]+)(?:\s+([\w\.,R\$]+))?(?:\s+(\d{1,2}:\d{2}))?', texto)
    if not match:
        update.message.reply_text('Formato inválido. Use: link "Título" preço_anterior preço_atual [HH:MM] ou link "Título" preço [HH:MM]')
        return

    link = match.group(1)
    titulo_manual = match.group(2)
    preco1 = match.group(3)
    preco2 = match.group(4)
    horario = match.group(5)

    precos = [preco1] if not preco2 else [preco1, preco2]

    link_encurtado = encurtar_link(link)
    titulo = gerar_titulo_criativo(titulo_manual)
    anuncio = criar_anuncio(link_encurtado, titulo, precos)

    if horario:
        try:
            agora = datetime.now(TZ)
            hora, minuto = map(int, horario.split(":"))
            agendamento = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)

            if agendamento <= agora:
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
        context.bot.send_message(chat_id=GRUPO_SAIDA_ID, text=anuncio)
        try:
            texto_tweet = anuncio.replace("\n", " ")
            if len(texto_tweet) > 280:
                texto_tweet = texto_tweet[:277] + "..."

def start(update, context):
    update.message.reply_text(
        'Envie: link "Título do Produto" preço_anterior preço_atual [HH:MM] '
        'ou link "Título do Produto" preço [HH:MM] no grupo de entrada.'
    )

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, processar_mensagem))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
