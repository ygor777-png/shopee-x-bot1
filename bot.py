from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import os

TOKEN = os.getenv("BOT_TOKEN")  # Defina a variável de ambiente no Railway

def start(update, context):
    update.message.reply_text("Me envie o link do produto para eu criar o anúncio!")

def criar_anuncio(update, context):
    link = update.message.text.strip()

    # Aqui você pode futuramente integrar com IA ou scraping para pegar título/preço
    titulo = "Oferta Imperdível 🔥"
    preco_anterior = "R$ 199,90"
    preco_atual = "R$ 99,90"

    anuncio = f"""
🔥 {titulo} 🔥

💰 De: {preco_anterior}  
✅ Por: {preco_atual}  

👉 Garanta aqui: {link}
"""
    update.message.reply_text(anuncio)

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, criar_anuncio))

    # Railway precisa rodar em polling
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
