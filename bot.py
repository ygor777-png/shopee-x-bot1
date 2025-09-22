from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os, re, random, pytz, pyshorteners, requests
from datetime import datetime, timedelta, time as dtime
import pandas as pd
from io import BytesIO
from urllib.parse import urlparse

# -------- Configurações --------
TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")  # token do Hugging Face
HF_MODEL = "google/flan-t5-large"  # modelo compatível com text-generation

GRUPO_ENTRADA_ID = int(os.getenv("GRUPO_ENTRADA_ID", "-4653176769"))
GRUPO_SAIDA_ID = int(os.getenv("GRUPO_SAIDA_ID", "-1001592474533"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "1420827874"))

TZ = pytz.timezone("America/Sao_Paulo")

LINK_CENTRAL = "https://atom.bio/ofertas_express"

CSV_LINKS = [link.strip() for link in os.getenv("CSV_URLS", "").split(",") if link.strip()]

enviados_global = set()
indice_global = 0

def achar(row, *possiveis_nomes):
    for nome in possiveis_nomes:
        if nome in row and not pd.isna(row[nome]) and str(row[nome]).strip():
            return str(row[nome]).strip()
    return ""

def encurtar_link(link):
    try:
        from urllib.parse import urlparse
        if not link or not urlparse(link).scheme.startswith("http"):
            print(f"⚠️ Link inválido, não será encurtado: {link}")
            return link
        s = pyshorteners.Shortener()
        return s.tinyurl.short(link)
    except Exception as e:
        print(f"Erro ao encurtar link: {e}")
        return link

def formatar_preco(valor):
    try:
        valor = re.sub(r'[^\d,\.]', '', str(valor))
        valor_float = float(valor.replace(',', '.'))
        return f"R$ {valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(valor)

def gerar_texto_preco(precos):
    if not precos:
        return "💰 Preço sob consulta"

    # Se houver dois preços e eles forem iguais, mantém só um
    if len(precos) == 2 and precos[0] == precos[1]:
        precos = [precos[0]]

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
    return f"""⚡ EXPRESS ACHOU, CONFIRA!! ⚡

{titulo}

{texto_preco}

👉 Compre por aqui: {link}

⚠️ Corre que acaba rápido!

🌐 Siga nossas redes sociais:
{LINK_CENTRAL}"""

async def start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Olá! Eu sou o bot de ofertas.\n"
        "Use /comandos para ver a lista de comandos disponíveis."
    )

async def comando_lista(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📜 *Comandos disponíveis:*\n"
        "/status - Mostra o status do bot\n"
        "/csv - Força o envio de um produto agora\n"
        "/comandos - Lista todos os comandos\n"
        "/start - Mensagem de boas-vindas",
        parse_mode="Markdown"
    )

async def comando_csv(update, context: ContextTypes.DEFAULT_TYPE):
    await enviar_produto(context)
    await update.message.reply_text("✅ Produto enviado manualmente.")

async def status(update, context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.now(TZ).strftime("%d/%m/%Y %H:%M:%S")
    jobs = context.job_queue.jobs()
    proxima_execucao = "—"

    if jobs:
        try:
            proxima_execucao_dt = jobs[0].next_t.astimezone(TZ)
            proxima_execucao = proxima_execucao_dt.strftime("%d/%m/%Y %H:%M:%S")
        except Exception as e:
            print(f"Erro ao calcular próxima execução: {e}")

    texto_status = (
        f"📊 *Status do Bot*\n\n"
        f"🕒 Horário atual: {agora}\n"
        f"🤖 Envio automático: {'✅ Ativo' if jobs else '❌ Inativo'}\n"
        f"📦 Produtos enviados nesta sessão: {len(enviados_global)}\n"
        f"⏭ Próxima execução: {proxima_execucao}"
    )

    await update.message.reply_text(texto_status, parse_mode="Markdown")

def processar_csv():
    global enviados_global

    todos_itens = []

    for link_csv in CSV_LINKS:
        try:
            resp = requests.get(link_csv)
            resp.raise_for_status()
            df = pd.read_csv(BytesIO(resp.content))

            # Garante que existe uma coluna ID única para evitar repetição
            if "ID" not in df.columns:
                df["ID"] = df.index

            # Filtra para não repetir itens já enviados
            df_filtrado = df[~df["ID"].isin(enviados_global)]

            # Adiciona à lista geral
            todos_itens.append(df_filtrado)
        except Exception as e:
            print(f"Erro ao processar CSV {link_csv}: {e}")

    if not todos_itens:
        print("Nenhum item disponível para envio.")
        return None

    # Junta todos os CSVs filtrados
    df_final = pd.concat(todos_itens, ignore_index=True)

    if df_final.empty:
        print("Todos os itens já foram enviados nesta sessão.")
        return None

    # Escolhe um item aleatório
    row = df_final.sample(n=1).iloc[0]
    enviados_global.add(row["ID"])

    return row
    
async def enviar_produto(context: ContextTypes.DEFAULT_TYPE):
    try:
        # Verifica se está dentro do horário permitido (07h às 23h)
        hora_atual = datetime.now(TZ).hour
        if hora_atual < 7 or hora_atual >= 23:
            print("⏸️ Fora do horário de postagem automática.")
            return

        row = processar_csv()
        if row is None:
            print("Nenhum produto para enviar.")
            return

        # Extrai dados do CSV usando a função achar
        link_produto = achar(row, "link", "url", "product_link", "produto_url", "url do produto")
        titulo_original = achar(row, "titulo", "title", "name", "produto", "product_name", "nome")
        preco_atual = achar(row, "preco", "sale_price", "valor", "current_price", "preço atual")
        preco_antigo = achar(row, "price", "old_price", "preco_original", "original_price", "preço original")
        imagem_url = achar(row, "imagem", "image_link", "img_url", "foto", "picture")

        # Monta lista de preços
        precos = []
        if preco_atual:
            precos.append(formatar_preco(preco_atual))
        if preco_antigo:
            precos.insert(0, formatar_preco(preco_antigo))

        # Monta anúncio com bordão fixo
        anuncio = f"""⚡ EXPRESS ACHOU, CONFIRA! ⚡

{titulo_original}

{gerar_texto_preco(precos)}

👉 Compre por aqui: {encurtar_link(link_produto)}

⚠️ Corre que acaba rápido!

🌐 Siga nossas redes sociais:
{LINK_CENTRAL}"""

        # Envia com imagem se houver
        if imagem_url and imagem_url.startswith("http"):
            await context.bot.send_photo(
                chat_id=GRUPO_SAIDA_ID,
                photo=imagem_url,
                caption=anuncio
            )
        else:
            await context.bot.send_message(
                chat_id=GRUPO_SAIDA_ID,
                text=anuncio
            )

        print(f"✅ Produto enviado: {titulo_original}")

    except Exception as e:
        print(f"Erro ao enviar produto: {e}")

job_envio = None  # variável global para controlar o agendamento

async def stop_csv(update, context: ContextTypes.DEFAULT_TYPE):
    global job_envio
    if job_envio:
        job_envio.schedule_removal()
        job_envio = None
        await update.message.reply_text("⏸️ Envio automático pausado.")
    else:
        await update.message.reply_text("⚠️ O envio automático já está pausado.")

async def play_csv(update, context: ContextTypes.DEFAULT_TYPE):
    global job_envio
    if not job_envio:
        job_envio = context.job_queue.run_repeating(
            enviar_produto,
            interval=60*10,  # a cada 10 minutos
            first=0
        )
        await update.message.reply_text("▶️ Envio automático retomado.")
    else:
        await update.message.reply_text("⚠️ O envio automático já está ativo.")

def main():
    global job_envio
    application = Application.builder().token(TOKEN).build()

    # Comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("comandos", comando_lista))
    application.add_handler(CommandHandler("csv", comando_csv))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("stopcsv", stop_csv))
    application.add_handler(CommandHandler("playcsv", play_csv))

    # Inicia agendamento automático imediatamente
    job_envio = application.job_queue.run_repeating(
        enviar_produto,
        interval=60*10,  # a cada 10 minutos
        first=0
    )

    print("🤖 Bot iniciado e agendamento configurado.")
    application.run_polling()

if __name__ == "__main__":
    main()
