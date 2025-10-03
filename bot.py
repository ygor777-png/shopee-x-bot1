import os
import requests
import pandas as pd
import random
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    MessageHandler, filters
)

# 🔹 Configurações
TOKEN = os.getenv("BOT_TOKEN")  # Token do bot
GRUPO_SAIDA_ID = int(os.getenv("GRUPO_SAIDA_ID", "-1001592474533"))
GRUPO_ENTRADA_ID = int(os.getenv("GRUPO_ENTRADA_ID", "-4653176769"))
CSV_URLS = os.getenv("CSV_URLS", "")
LINK_CENTRAL = os.getenv("https://atom.bio/ofertas_express", "https://atom.bio/ofertas_express")

# 🔹 Fila de produtos
fila_shopee = []

# 🔹 Controle de postagem automática
auto_post_shopee = True

# 🔹 Fuso horário
TZ = pytz.timezone("America/Sao_Paulo")

# 🔹 Controle de repetição
produtos_postados = set()

# 🔗 Encurtador de links (TinyURL)
def encurtar_link(url):
    try:
        api_url = f"http://tinyurl.com/api-create.php?url={url}"
        r = requests.get(api_url)
        if r.status_code == 200:
            return r.text.strip()
        else:
            print("Erro ao encurtar link:", r.text)
            return url
    except Exception as e:
        print("Erro no encurtador:", e)
        return url

def achar(row, *keys):
    for key in keys:
        for col in row.index:
            if col.strip().lower() == key.strip().lower() and pd.notna(row[col]):
                return str(row[col]).strip()
    return None

def formatar_preco(valor):
    try:
        valor = str(valor).replace(",", ".")
        return f"R${float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return valor

def criar_anuncio(link, titulo, precos):
    precos_txt = " ➡ ".join(precos) if precos else ""
    return f"""⚡ EXPRESS ACHOU, CONFIRA! ⚡

{titulo}

💰 {precos_txt}

👉 Compre por aqui: {link}

⚠️ Corre que acaba rápido!

🌐 Link para entrar no grupo:
{LINK_CENTRAL}"""

def postar_shopee():
    """Seleciona um produto aleatório do CSV ainda não postado e adiciona à fila."""
    try:
        if not CSV_URLS:
            print("⚠️ Nenhuma URL de CSV configurada.")
            return

        print(f"📂 Lendo CSV da URL: {CSV_URLS}")
        df = pd.read_csv(CSV_URLS)

        # Embaralha as linhas para pegar aleatório
        df = df.sample(frac=1).reset_index(drop=True)

        for _, row in df.iterrows():
            link = achar(row, "Product Link", "product_link", "Link", "product_short_link")
            if not link or link in produtos_postados:
                continue

            # 🔗 encurta o link antes de postar
            link = encurtar_link(link)

            titulo = achar(row, "Product Name", "Título", "title")
            preco1 = achar(row, "price", "old_price", "preco_original", "original_price", "preço original")
            preco2 = achar(row, "preco", "sale_price", "valor", "current_price", "preço atual")
            imagem = achar(row, "imagem", "image_link", "img_url", "foto", "picture")

            precos = []
            if preco1:
                precos.append(formatar_preco(preco1))
            if preco2 and preco2 != preco1:
                precos.append(formatar_preco(preco2))

            anuncio = criar_anuncio(link, titulo, precos)

            fila_shopee.append({
                "titulo": titulo,
                "imagem": imagem,
                "anuncio": anuncio
            })

            produtos_postados.add(link)
            print(f"✅ Produto Shopee adicionado à fila: {titulo}")
            break

    except Exception as e:
        print(f"Erro ao ler CSV da Shopee: {e}")

async def enviar_shopee(context: ContextTypes.DEFAULT_TYPE):
    """Envia o próximo produto da fila para o grupo do Telegram."""
    try:
        if not fila_shopee:
            print("⚠️ Nenhum produto Shopee na fila para enviar.")
            return

        produto = fila_shopee.pop(0)
        if produto["imagem"] and produto["imagem"].startswith("http"):
            await context.bot.send_photo(
                chat_id=GRUPO_SAIDA_ID,
                photo=produto["imagem"],
                caption=produto["anuncio"]
            )
        else:
            await context.bot.send_message(
                chat_id=GRUPO_SAIDA_ID,
                text=produto["anuncio"]
            )
        print(f"📤 Shopee enviado: {produto['titulo']}")

    except Exception as e:
        print(f"Erro ao enviar Shopee: {e}")

# 🔄 Ciclo de postagem automática
async def ciclo_postagem(context: ContextTypes.DEFAULT_TYPE):
    hora_atual = datetime.now(TZ).hour
    if 7 <= hora_atual <= 23 and auto_post_shopee:
        if not fila_shopee:  # se não houver manual, puxa Shopee
            postar_shopee()
        await enviar_shopee(context)
    else:
        print("⏸️ Fora do horário de postagem ou automático pausado.")

# 📂 Comando manual para postar Shopee
async def comando_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    postar_shopee()
    await enviar_shopee(context)
    await update.message.reply_text("📂 Produto Shopee postado manualmente.")

# 📊 Status do bot
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = context.job_queue.get_jobs_by_name("ciclo_postagem")
    if jobs:
        proxima_exec = jobs[0].next_t.astimezone(TZ).strftime("%H:%M")
    else:
        proxima_exec = "Não agendado"

    texto_status = (
        f"📊 *Status do Bot*\n"
        f"🛒 Shopee na fila: {len(fila_shopee)}\n"
        f"⏰ Horário atual: {datetime.now(TZ).strftime('%H:%M')}\n"
        f"⚙️ Postagem automática: {'✅ Ligada' if auto_post_shopee else '⏸️ Pausada'}\n"
        f"🕒 Próxima postagem: {proxima_exec}"
    )
    await update.message.reply_text(texto_status, parse_mode="Markdown")

# ⏸️ Pausar envio automático
async def stop_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global auto_post_shopee
    auto_post_shopee = False
    await update.message.reply_text("⏸️ Envio automático da Shopee pausado.")

# ▶️ Retomar envio automático
async def play_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global auto_post_shopee
    auto_post_shopee = True
    await update.message.reply_text("▶️ Envio automático da Shopee retomado.")

# 🤖 Comando /start explicativo
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "🤖 *Bem-vindo ao Bot de Ofertas!*\n\n"
        "Aqui está o que você pode fazer:\n\n"
        "📂 */csv* → Posta manualmente um produto da Shopee (do CSV)\n"
        "📊 */status* → Mostra status do bot (fila, horário, próximo envio)\n"
        "⏸️ */stopcsv* → Pausa o envio automático\n"
        "▶️ */playcsv* → Retoma o envio automático\n\n"
        "📝 *Como mandar produtos manualmente no grupo de entrada:*\n"
        "Envie a mensagem exatamente neste formato:\n\n"
        "`Link do produto`\n"
        "`Título do produto`\n"
        "`Valor antes e depois` (ou apenas um valor)\n"
        "`Cupom` (opcional)\n\n"
        "➡️ Se você incluir um cupom, o anúncio será formatado destacando o desconto no Mercado Livre. "
        "Se não incluir, ele segue o padrão normal.\n\n"
        "⚡ O bot sempre dá prioridade ao que você mandar manualmente. "
        "Se não houver nada, ele posta automaticamente da Shopee a cada 10 minutos."
    )
    await update.message.reply_text(texto, parse_mode="Markdown")

# 📥 Handler para mensagens no grupo de entrada
async def entrada_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_ENTRADA_ID:
        return  # só reage no grupo de entrada

    texto = update.message.text.strip().split("\n")
    if len(texto) < 3:
        return  # formato inválido

    link = encurtar_link(texto[0])  # 🔗 encurta o link manual também
    titulo = texto[1]
    valor = texto[2]
    cupom = texto[3] if len(texto) > 3 else None

    if cupom:
        anuncio = f"""⚡ EXPRESS ACHOU, CONFIRA! ⚡

CUPOM + {valor} no Mercado Livre: "{cupom}"

🌐 Link para entrar no grupo:
{LINK_CENTRAL}

⚠️ Corre que acaba rápido!"""
    else:
        anuncio = f"""⚡ EXPRESS ACHOU, CONFIRA! ⚡

{titulo}

💰 {valor}

👉 Compre por aqui: {link}

⚠️ Corre que acaba rápido!

🌐 Link para entrar no grupo:
{LINK_CENTRAL}"""

    # insere no início da fila = prioridade
    fila_shopee.insert(0, {
        "titulo": titulo,
        "imagem": None,
        "anuncio": anuncio
    })

    await update.message.reply_text("✅ Produto manual adicionado à fila com prioridade.")

# 🚀 Função principal
def main():
    application = Application.builder().token(TOKEN).build()

    # Handlers de comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("csv", comando_csv))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("stopcsv", stop_csv))
    application.add_handler(CommandHandler("playcsv", play_csv))

    # Handler para mensagens no grupo de entrada
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, entrada_handler))

    # Agendamento de postagens automáticas
    application.job_queue.run_repeating(
        ciclo_postagem,
        interval=60*10,  # a cada 10 minutos
        first=0,
        name="ciclo_postagem"
    )

    print("🤖 Bot iniciado e agendamento configurado.")
    application.run_polling()


if __name__ == "__main__":
    main()
