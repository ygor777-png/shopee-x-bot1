from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import os, requests, re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

TOKEN = os.getenv("BOT_TOKEN")

# Substitua pelos IDs reais dos grupos
GRUPO_ENTRADA_ID = -4653176769  # Grupo onde você manda os links
GRUPO_SAIDA_ID = -1001592474533   # Grupo onde o bot posta os anúncios

# -------- Funções de scraping --------
def extrair_dados_shopee(link):
    try:
        r = requests.get(link, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")

        # Título do produto
        titulo = soup.find("meta", property="og:title")
        titulo = titulo["content"].strip() if titulo else "Produto sem título"

        # Preço atual (vem no og:description ou em spans)
        preco_atual = None
        desc = soup.find("meta", property="og:description")
        if desc:
            match = re.search(r"R\$ ?\d+[\.,]?\d*", desc["content"])
            if match:
                preco_atual = match.group(0)

        # Preço anterior (tentativa de pegar o primeiro valor diferente)
        preco_anterior = None
        spans = soup.find_all("span")
        for s in spans:
            txt = s.get_text()
            if "R$" in txt:
                if not preco_anterior:
                    preco_anterior = txt
                elif not preco_atual:
                    preco_atual = txt

        return titulo, preco_anterior or "N/A", preco_atual or "N/A"
    except Exception as e:
        print("Erro ao extrair Shopee:", e)
        return "Produto", "N/A", "N/A"

def extrair_dados_generico(link):
    try:
        r = requests.get(link, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        titulo = soup.title.string.strip() if soup.title else "Produto"
        return titulo[:80], "N/A", "N/A"
    except:
        return "Produto", "N/A", "N/A"

def extrair_dados(link):
    if "shopee.com" in link:
        return extrair_dados_shopee(link)
    else:
        return extrair_dados_generico(link)

# -------- Criação do anúncio --------
def criar_anuncio(link, titulo, preco_anterior, preco_atual):
    return f"""
🔥 {titulo} 🔥

💰 De: {preco_anterior}  
✅ Por: {preco_atual}  

👉 Garanta aqui: {link}
"""

# -------- Processamento da mensagem --------
def processar_mensagem(update, context):
    if not update.message or not update.message.text:
        return  

    if update.message.chat_id != GRUPO_ENTRADA_ID:
        return

    texto = update.message.text.strip()

    # Regex para capturar link + horário opcional (HH:MM)
    match = re.match(r"(https?://\S+)(?:\s+(\d{1,2}:\d{2}))?", texto)
    if not match:
        update.message.reply_text("Formato inválido. Envie: link [HH:MM]")
        return

    link = match.group(1)
    horario = match.group(2)

    # Extrai dados reais
    titulo, preco_anterior, preco_atual = extrair_dados(link)
    anuncio = criar_anuncio(link, titulo, preco_anterior, preco_atual)

    if horario:
        try:
            agora = datetime.now()
            hora, minuto = map(int, horario.split(":"))
            agendamento = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)

            if agendamento < agora:
                agendamento += timedelta(days=1)

            delay = (agendamento - agora).total_seconds()

            context.job_queue.run_once(
                lambda ctx: ctx.bot.send_message(chat_id=GRUPO_SAIDA_ID, text=anuncio),
                delay
            )

            update.message.reply_text(f"✅ Link agendado para {agendamento.strftime('%H:%M')} com título: {titulo}")
        except:
            update.message.reply_text("⚠️ Horário inválido. Use formato HH:MM")
    else:
        context.bot.send_message(chat_id=GRUPO_SAIDA_ID, text=anuncio)
        update.message.reply_text(f"✅ Link enviado imediatamente com título: {titulo}")

def start(update, context):
    update.message.reply_text("Envie: link [HH:MM] no grupo de entrada.")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, processar_mensagem))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
