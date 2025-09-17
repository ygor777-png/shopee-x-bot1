from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import os, requests, re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

TOKEN = os.getenv("BOT_TOKEN")

# Coloque valores provisórios, vamos descobrir os IDs reais no log
GRUPO_ENTRADA_ID = -1001234567890
GRUPO_SAIDA_ID = -1009876543210

def extrair_titulo(link):
    try:
        r = requests.get(link, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        titulo = soup.title.string.strip()
        return titulo[:80]
    except:
        return "Oferta Especial! 🔥"

def criar_anuncio(link, titulo):
    preco_anterior = "R$ 199,90"
    preco_atual = "R$ 99,90"

    return f"""
🔥 {titulo} 🔥

💰 De: {preco_anterior}  
✅ Por: {preco_atual}  

👉 Garanta aqui: {link}
"""

def processar_mensagem(update, context):
    # DEBUG: imprime tudo que chega
    if update.message:
        print("📩 Mensagem recebida:")
        print("Chat ID:", update.message.chat_id)
        print("Texto:", update.message.text)

    if not update.message or not update.message.text:
        return  

    # Só processa se for do grupo de entrada
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

    titulo = extrair_titulo(link)
    anuncio = criar_anuncio(link, titulo)

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

            update.message.reply_text(f"✅ Link agendado para {agendamento.strftime('%H:%M')}")
        except:
            update.message.reply_text("⚠️ Horário inválido. Use formato HH:MM")
    else:
        context.bot.send_message(chat_id=GRUPO_SAIDA_ID, text=anuncio)
        update.message.reply_text("✅ Link enviado imediatamente")

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
