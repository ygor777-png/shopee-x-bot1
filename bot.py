from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os, re, random, pytz, pyshorteners, requests
from datetime import datetime, timedelta, time as dtime
import pandas as pd
from io import BytesIO
from huggingface_hub import InferenceClient  # IA gratuita

# -------- Configurações --------
TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")  # token do Hugging Face
HF_MODEL = "google/flan-t5-large"  # modelo gratuito

GRUPO_ENTRADA_ID = int(os.getenv("GRUPO_ENTRADA_ID", "-4653176769"))
GRUPO_SAIDA_ID = int(os.getenv("GRUPO_SAIDA_ID", "-1001592474533"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "1420827874"))

TZ = pytz.timezone("America/Sao_Paulo")

LINK_CENTRAL = "https://atom.bio/ofertas_express"

CSV_LINKS = [link.strip() for link in os.getenv("CSV_URLS", "").split(",") if link.strip()]

enviados_global = set()
indice_global = 0

def encurtar_link(link):
    try:
        s = pyshorteners.Shortener()
        return s.tinyurl.short(link)
    except:
        return link

def _sanitizar_linha(texto: str) -> str:
    if not texto:
        return ""
    t = texto.strip()
    t = t.replace("Título:", "").replace("Titulo:", "")
    t = t.strip(' "\'“”‘’`')
    lixos = ["aqui está", "aqui vai", "título sugerido", "sugestão de título", "headline", "título:"]
    tl = t.lower()
    if any(x in tl for x in lixos) and ":" in t:
        t = t.split(":", 1)[-1].strip()
    return t[:80]

def gerar_titulo_descontraido_ia(titulo_original):
    try:
        client = InferenceClient(model=HF_MODEL, token=HF_TOKEN)
        prompt = (
            "Escreva apenas uma frase curta (máx. 10 palavras), descontraída e chamativa, "
            "sem emojis, que resuma este produto em português do Brasil. "
            "Não repita o título, não adicione rótulos como 'Título:'. "
            f"\nProduto: {titulo_original}\n"
            "Responda somente com a frase curta."
        )
        resposta = client.text_generation(
            prompt,
            max_new_tokens=32,
            temperature=0.8,
            do_sample=True
        )
        linha_curta = _sanitizar_linha(resposta.splitlines()[0] if resposta else "")
        if not linha_curta:
            linha_curta = "Pra deixar seu dia mais prático"
        return linha_curta
    except Exception as e:
        print(f"Erro Hugging Face: {e}")
        return "Oferta especial pra você"

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
        preco_antigo, preco_atual = precos
        modelos = [
            f"💰 De: {preco_antigo}\n✅ Por: {preco_atual}",
            f"💸 Antes {preco_antigo}, agora só {preco_atual}!",
            f"🔥 De {preco_antigo} caiu para {preco_atual}!",
            f"🎉 De {preco_antigo} por apenas {preco_atual}!",
            f"➡️ Aproveite: {preco_antigo} → {preco_atual}"
        ]
        return random.choice(modelos)

def criar_anuncio(link, titulo, precos):
    texto_preco = gerar_texto_preco(precos)
    return f"""{titulo}

{texto_preco}

👉 Compre por aqui: {link}

⚠️ Corre que acaba rápido!

🌐 Siga nossas redes sociais:
{LINK_CENTRAL}"""

def mapear_colunas(df):
    colunas = {c.lower(): c for c in df.columns}

    def achar(*possiveis):
        for p in possiveis:
            if p in colunas:
                return colunas[p]
        return None

    return {
        "link": achar("link", "url", "product_link", "produto_url", "url do produto"),
        "titulo": achar("titulo", "title", "name", "produto", "product_name", "nome"),
        "preco": achar("preco", "sale_price", "valor", "current_price", "preço atual"),
        "preco_antigo": achar("price", "old_price", "preco_original", "original_price", "preço original"),
        "imagem": achar("imagem", "锘縤mage_link", "img_url", "image_link_3", "picture")
    }

async def processar_csv(context: ContextTypes.DEFAULT_TYPE):
    global enviados_global, indice_global

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

            if indice_global >= len(df):
                indice_global = 0

            row = df.iloc[indice_global]
            indice_global += 1

            link_produto = str(row[mapeamento["link"]]).strip()
            if link_produto in enviados_global:
                return
            enviados_global.add(link_produto)

            titulo_manual = str(row[mapeamento["titulo"]]).strip()
            preco_atual = formatar_preco(row[mapeamento["preco"]])
            preco_antigo = None
            if mapeamento["preco_antigo"] and pd.notna(row[mapeamento["preco_antigo"]]):
                preco_antigo = formatar_preco(row[mapeamento["preco_antigo"]])

            if preco_antigo and preco_antigo != preco_atual:
                precos = [preco_antigo, preco_atual]
            else:
                precos = [preco_atual]

            titulo_curto = gerar_titulo_descontraido_ia(titulo_manual)
            titulo_final = f"{titulo_curto}\n\n{titulo_manual}"

            link_encurtado = encurtar_link(link_produto)
            anuncio = criar_anuncio(link_encurtado, titulo_final, precos)

            link_imagem = None
            if mapeamento["imagem"] and pd.notna(row[mapeamento["imagem"]]):
                link_imagem = str(row[mapeamento["imagem"]]).strip()

            if link_imagem:
                await context.bot.send_photo(chat_id=GRUPO_SAIDA_ID, photo=link_imagem, caption=anuncio)
            else:
                await context.bot.send_message(chat_id=GRUPO_SAIDA_ID, text=anuncio)

            return

        except Exception as e:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ Erro ao processar CSV {url_csv}: {e}")

async def comando_csv(update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID:
        await update.message.reply_text("❌ Você não tem permissão para usar este comando.")
        return
    await update.message.reply_text("📦 Iniciando envio manual do CSV...")
    await processar_csv(context)
    await update.message.reply_text("✅ Envio manual do CSV concluído!")

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

async def playcsv(update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID:
        await update.message.reply_text("❌ Você não tem permissão para usar este comando.")
        return

    jobs = context.job_queue.get_jobs_by_name("csv_intervalo")
    if jobs:
        await update.message.reply_text("⚠️ O envio automático já está ativo.")
        return

    context.job_queue.run_repeating(
        enviar_csv_intervalo,
        interval=600,  # 10 minutos
        first=0,       # começa imediatamente
        name="csv_intervalo"
    )
    await update.message.reply_text("▶️ Envio automático do CSV reativado!")

async def comandos(update, context: ContextTypes.DEFAULT_TYPE):
    lista = (
        "📜 *Comandos disponíveis:*\n\n"
        "/start - Instruções de uso\n"
        "/csv - Enviar ofertas do CSV agora (admin)\n"
        "/stopcsv - Parar envio automático (admin)\n"
        "/playcsv - Retomar envio automático (admin)\n"
        "/status - Verificar status do bot\n"
        "/comandos - Mostrar esta lista\n"
    )
    await update.message.reply_text(lista, parse_mode="Markdown")

async def status(update, context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S")
    jobs = context.job_queue.get_jobs_by_name("csv_intervalo")
    status_envio = "✅ Ativo" if jobs else "⛔ Parado"
    total_enviados = len(enviados_global)

    proxima_execucao = "—"
    if jobs:
        try:
            proxima_execucao = jobs[0].next_t.strftime("%d/%m/%Y %H:%M:%S")
        except:
            pass

    texto = (
        f"📊 *Status do Bot*\n\n"
        f"🕒 Horário atual: {agora}\n"
        f"📦 Envio automático: {status_envio}\n"
        f"📤 Produtos enviados nesta sessão: {total_enviados}\n"
        f"⏭ Próxima execução: {proxima_execucao}"
    )

    await update.message.reply_text(texto, parse_mode="Markdown")

async def enviar_csv_intervalo(context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.now(TZ).time()
    if dtime(8, 0) <= agora <= dtime(23, 0):
        await processar_csv(context)

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
    titulo_curto = gerar_titulo_descontraido_ia(titulo_manual)
    titulo_final = f"{titulo_curto}\n\n{titulo_manual}"
    anuncio = criar_anuncio(link_encurtado, titulo_final, precos)

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
                f"✅ Link agendado para {agendamento.strftime('%H:%M')} com título: {titulo_manual}"
            )
        except Exception as e:
            await update.message.reply_text(f"⚠️ Horário inválido. Erro: {e}")
    else:
        await context.bot.send_message(chat_id=GRUPO_SAIDA_ID, text=anuncio)
        await update.message.reply_text(f"✅ Link enviado imediatamente com título: {titulo_manual}")

async def start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'Envie: link "Título" preço_anterior preço_atual [HH:MM] ou link "Título" preço [HH:MM]\n'
        'Use /csv para enviar manualmente as ofertas do CSV agora (somente admin).\n'
        'Use /stopcsv para parar o envio automático.\n'
        'Use /playcsv para retomar o envio automático.\n'
        'Use /status para ver o status do bot.\n'
        'Use /comandos para ver todos os comandos.'
    )

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("csv", comando_csv))
    application.add_handler(CommandHandler("stopcsv", stopcsv))
    application.add_handler(CommandHandler("playcsv", playcsv))
    application.add_handler(CommandHandler("comandos", comandos))
    application.add_handler(CommandHandler("status", status))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, processar_mensagem))

    application.job_queue.run_repeating(
        enviar_csv_intervalo,
        interval=60,
        first=0,
        name="csv_intervalo"
    )

    application.run_polling()

if __name__ == "__main__":
    main()
