import os
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Função para extrair dados do produto
def extrair_dados(link):
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(link, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')

    nome = soup.find('title').text.strip()
    preco_tags = soup.find_all('div', class_='pmm-price-original')
    preco_original = preco_tags[0].text.strip() if preco_tags else "Não encontrado"
    preco_promocional = soup.find('div', class_='pmm-price-final').text.strip() if soup.find('div', class_='pmm-price-final') else "Não encontrado"

    return {
        'nome': nome,
        'preco_original': preco_original,
        'preco_promocional': preco_promocional
    }

# Função para gerar título criativo (placeholder)
def gerar_titulo(nome):
    return f"{nome} — Segurança inteligente por um precinho!"

# Função principal do bot
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text
    if "shopee.com.br" in link:
        dados = extrair_dados(link)
        titulo = gerar_titulo(dados['nome'])

        anuncio = f"""
🎁 Produto: {titulo}
🔥 De: {dados['preco_original']}
💰 Por: {dados['preco_promocional']}

🛒 Compre aqui: {link}
"""
        await update.message.reply_text(anuncio)

# Inicialização do bot
def main():
    token = os.getenv("TELEGRAM_TOKEN")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    app.run_polling()

if __name__ == "__main__":
    main()
