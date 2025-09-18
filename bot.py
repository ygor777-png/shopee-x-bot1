from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import os, re, random, pytz, pyshorteners, requests, time as time_module
from datetime import datetime, timedelta, time
import pandas as pd
from io import BytesIO

# -------- Configurações --------
TOKEN = os.getenv("BOT_TOKEN")

GRUPO_ENTRADA_ID = int(os.getenv("GRUPO_ENTRADA_ID", "-4653176769"))
GRUPO_SAIDA_ID = int(os.getenv("GRUPO_SAIDA_ID", "-1001592474533"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "1420827874"))

TZ = pytz.timezone("America/Sao_Paulo")

LINK_CENTRAL = "https://atom.bio/ofertas_express"

# Lista de links CSV (separe por vírgula no .env)
CSV_LINKS = [link.strip() for link in os.getenv("CSV_URLS", "").split(",") if link.strip()]

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
        "🎉 Oferta Especial:"
    ]
    return f"{random.choice(prefixos)} {titulo_manual}"

def gerar_texto_preco(precos):
    if len(precos) == 1:
        preco = precos[0]
        modelos_unico = [
            f"💰 Por: {preco}",
            f"🔥 Apenas {preco}!",
            f"🎯 Leve já por {preco}!",
            f"⚡ Oferta: {preco}",
            f"✅ Agora por {preco}"
        ]
        return random.choice(modelos_unico)
    else:
        preco_anterior, preco_atual = precos
        modelos = [
            f"💰 De: {preco_anterior}\n✅ Por: {preco_atual}",
            f"💸 Antes {preco_anterior}, agora só {preco_atual}!",
            f"🔥 De {preco_anterior} caiu para {preco_atual}!",
            f"🎉 De {preco_anterior} por apenas {preco_atual}!",
            f"➡️ Aproveite: {preco_anterior} → {preco_atual}"
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

# -------- Envio --------
def enviar_anuncio(context):
    job = context.job
    anuncio = job.context["anuncio"]
    context.bot.send_message(chat_id=job.context["chat_id"], text=anuncio)

# -------- Mensagens manuais --------
def processar_mensagem(update, context):
    if not update.message or not update.message.text:
        return
    if update.message.chat_id != GRUPO_ENTRADA_ID:
        return

    texto = update.message.text.strip()
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
            update.message.reply_text(f"⚠️ Horário inválido. Erro: {e}")
    else:
        context.bot.send_message(chat_id=GRUPO_SAIDA_ID, text=anuncio)
        update.message.reply_text(f"✅ Link enviado imediatamente com título: {titulo}")

# -------- CSV automático --------
def processar_csv(context):
    enviados = set()
    for url_csv in CSV_LINKS:
        try:
            resp = requests.get(url_csv)
            df = pd.read_csv(BytesIO(resp.content))

            for _, row in df.iterrows():
                link_produto = str(row["link"]).strip()
                if link_produto in enviados:
                    continue
                enviados.add(link_produto)

                titulo_manual = str(row["titulo"]).strip()
                preco_atual = str(row["preco"]).strip()
                preco_antigo = str(row["preco_antigo"]).strip() if "preco_antigo" in row and pd.notna(row["preco_antigo"]) else None

                precos = [preco_atual] if not preco_antigo else [preco_antigo, preco_atual]
                link_encurtado = encurtar_link(link_produto)
                titulo = gerar_titulo_criativo(titulo_manual)
                anuncio = criar_anuncio(link_encurtado, titulo, precos)

                context.bot.send_message(chat_id=GRUPO_SAIDA_ID, text=anuncio)
                time_module.sleep(5)  # intervalo entre envios
        except Exception as e:
            context.bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ Erro ao processar CSV {url_csv}: {e}")

# -------- Comando manual para rodar CSV --------
def comando_csv(update, context):
    update.message.reply_text("📦 Iniciando envio manual do CSV...")
    processar_csv(context)
    update.message.reply_text("✅ Envio manual do CSV concluído!")

# -------- Inicialização --------
def start(update, context):
    update.message.reply_text(
        'Envie: link "Título" preço_anterior preço_atual [HH:MM] ou link "Título" preço [HH:MM]\n'
        'Use /csv para enviar manualmente as ofertas do CSV agora.'
    )

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("csv", comando_csv))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, processar_mensagem))

    # Agendar CSV diário às 9h
    updater.job_queue.run_daily(processar_csv, time=time(hour=9, minute=0, tzinfo=TZ))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
