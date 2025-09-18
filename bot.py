from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os, re, random, pytz, pyshorteners, requests, time as time_module
from datetime import datetime, timedelta, time as dtime
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

def formatar_preco(valor):
    try:
        valor = re.sub(r'[^\d,\.]', '', str(valor))
        valor_float = float(valor.replace(',', '.'))
        return f"R$ {valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(valor)

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

# -------- Mapeamento automático de colunas --------
def mapear_colunas(df):
    colunas = {c.lower(): c for c in df.columns}

    def achar(*possiveis):
        for p in possiveis:
            if p in colunas:
                return colunas[p]
        return None

    return {
        "link": achar("link", "product_link", "produto_url", "url do produto"),
        "titulo": achar("titulo", "title", "name", "produto", "product_name", "nome"),
        "preco": achar("sale_price", "price", "valor", "current_price", "preço atual"),
        "preco_antigo": achar("price", "old_price", "preco_original", "original_price", "preço original")
    }

# -------- Processar CSV --------
async def processar_csv(context: ContextTypes.DEFAULT_TYPE):
    enviados = set()
    for url_csv in CSV_LINKS:
        try:
            resp = requests.get(url_csv)
            df = pd.read_csv(BytesIO(resp.content))

            mapeamento = mapear_colunas(df)
            if not mapeamento["link"] or not mapeamento["titulo"] or not mapeamento["preco"]:
                colunas_encontradas = ", ".join(df.columns)
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=(
                        f"⚠️ CSV {url_csv} não tem colunas necessárias.\n"
                        f"Colunas encontradas: {colunas_encontradas}"
                    )
                )
                continue

            for _, row in df.iterrows():
                link_produto = str(row[mapeamento["link"]]).strip()
                if link_produto in enviados:
                    continue
                enviados.add(link_produto)

                titulo_manual = str(row[mapeamento["titulo"]]).strip()
                preco_atual = formatar_preco(row[mapeamento["preco"]])
                preco_antigo = None
                if mapeamento["preco_antigo"] and pd.notna(row[mapeamento["preco_antigo"]]):
                    preco_antigo = formatar_preco(row[mapeamento["preco_antigo"]])

                precos = [preco_atual] if not preco_antigo else [preco_antigo, preco_atual]
                link_encurtado = encurtar_link(link_produto)
                titulo = gerar_titulo_criativo(titulo_manual)
                anuncio = criar_anuncio(link_encurtado, titulo, precos)

                await context.bot.send_message(chat_id=GRUPO_SAIDA_ID, text=anuncio)
                time_module.sleep(5)  # intervalo entre envios
        except Exception as e:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ Erro ao processar CSV {url_csv}: {e}")

# -------- Comando manual para rodar CSV --------
async def comando_csv(update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID:
        await update.message.reply_text("❌ Você não tem permissão para usar este comando.")
        return
    await update.message.reply_text("📦 Iniciando envio manual do CSV...")
    await processar_csv(context)
    await update.message.reply_text("✅ Envio manual do CSV concluído!")

# -------- Parar agendamento --------
async def stopcsv(update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID:
        await update.message.reply_text("❌ Você não tem permissão para usar este comando.")
        return
    jobs = context.job_queue.get_jobs_by_name("csv_intervalo")
    if not jobs:
        await update.message.reply_text("⚠️ Nenhum agendamento ativo encontrado.")
        return
    for job in jobs:
        job.schedule_removal()
    await update.message.reply_text("🛑 Agendamento de envio automático cancelado.")

# -------- Envio automático a cada 10 minutos --------
async def enviar_csv_intervalo(context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.now(TZ).time()
    if dtime(8, 0) <= agora <= dtime(23, 0):
        await processar_csv(context)

# -------- Mensagens manuais --------
async def processar_mensagem(update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if update.effective_chat.id != GRUPO_ENTRADA_ID:
        return

    texto = update.message.text.strip()
    match = re.match(r'(https?://\S+)\s+"([^"]+)"\s+([\w\.,R\$]+)(?:\s+([\w\.,R\$]+))?(?:\s+(\d{1,2}:\d{2}))?', texto)
    if not match:
        await update.message.reply_text(
            'Formato inválido. Use: link "Título" preço_anterior preço_atual [HH:MM] ou link "Título" preço [HH:MM]'
        )
        return

    link = match.group(1)
    titulo_manual = match.group(2)
    preco1 = formatar_preco(match.group(3))
    preco2 = formatar_preco(match.group(4)) if match.group(4) else None
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
                lambda ctx: ctx.bot.send_message(chat_id=GRUPO_SAIDA_ID, text=anuncio),
                delay
            )
            await update.message.reply_text(
                f"✅ Link agendado para {agendamento.strftime('%H:%M')} com título: {titulo}"
            )
        except Exception as e:
            await update.message.reply_text(f"⚠️ Horário inválido. Erro: {e}")
    else:
        await context.bot.send_message(chat_id=GRUPO_SAIDA_ID, text=anuncio)
        await update.message.reply_text(f"✅ Link enviado imediatamente com título: {titulo}")

# -------- Comando /start --------
async def start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'Envie: link "Título" preço_anterior preço_atual [HH:MM] ou link "Título" preço [HH:MM]\n'
        'Use /csv para enviar manualmente as ofertas do CSV agora (somente admin).\n'
        'Use /stopcsv para parar o envio automático.'
    )

# -------- Função principal --------
def main():
    application = Application.builder().token(TOKEN).build()

    # Handlers de comando
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("csv", comando_csv))
    application.add_handler(CommandHandler("stopcsv", stopcsv))

    # Handler de mensagens manuais
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, processar_mensagem))

    # Agendamento de envio a cada 10 minutos entre 8h e 23h
    application.job_queue.run_repeating(
        enviar_csv_intervalo,
        interval=600,  # 10 minutos
        first=dtime(hour=8, minute=0, tzinfo=TZ),
        name="csv_intervalo"
    )

    application.run_polling()

if __name__ == "__main__":
    main
