import os
import re
import requests
import pandas as pd
import random
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Configurações
TOKEN = os.getenv("BOT_TOKEN")
GRUPO_SAIDA_ID = int(os.getenv("GRUPO_SAIDA_ID", "-1001592474533"))
CSV_URLS = os.getenv("CSV_URLS", "")
LINK_CENTRAL = os.getenv("LINK_CENTRAL", "https://atom.bio/ofertas_express")
fila_shopee = []
auto_post_shopee = True
TZ = pytz.timezone("America/Sao_Paulo")

# Funções utilitárias
def achar(row, *keys):
    for key in keys:
        if key in row and pd.notna(row[key]):
            return str(row[key]).strip()
    return None

def formatar_preco(valor):
    try:
        valor = str(valor).replace(",", ".")
        return f"R${float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return valor

def encurtar_link(link):
    try:
        r = requests.get(f"http://tinyurl.com/api-create.php?url={link}", timeout=10)
        if r.status_code == 200:
            return r.text
    except:
        pass
    return link

def criar_anuncio(link, titulo, precos):
    precos_txt = " ➡ ".join(precos) if precos else ""
    return f"""⚡ EXPRESS ACHOU, CONFIRA! ⚡

{titulo}

💰 {precos_txt}

👉 Compre por aqui: {link}

⚠️ Corre que acaba rápido!

🌐 Siga nossas redes sociais:
{LINK_CENTRAL}"""

# Shopee
def postar_shopee():
    try:
        if not CSV_URLS:
            print("⚠️ Nenhuma URL de CSV configurada.")
            return

        print(f"📂 Lendo CSV da URL: {CSV_URLS}")
        df = pd.read_csv(CSV_URLS)

        # Escolhe produto aleatório
        row = df.sample(n=1).iloc[0]

        titulo = achar(row, "titulo", "title", "name", "produto", "product_name", "nome")
        preco1 = achar(row, "price", "old_price", "preco_original", "original_price", "preço original")
        preco2 = achar(row, "preco", "sale_price", "valor", "current_price", "preço atual")
        link = achar(row, "link", "url", "product_link", "produto_url", "url do produto")

        if not titulo or not link:
            print("⚠️ Produto inválido no CSV.")
            return

        link_encurtado = encurtar_link(link)
        precos = []
        if preco1:
            precos.append(formatar_preco(preco1))
        if preco2 and preco2 != preco1:
            precos.append(formatar_preco(preco2))

        anuncio = criar_anuncio(link_encurtado, titulo, precos)
        imagem = achar(row, "imagem", "image_link", "img_url", "foto", "picture")

        fila_shopee.append({
            "titulo": titulo,
            "imagem": imagem,
            "anuncio": anuncio
        })
        print(f"✅ Produto Shopee adicionado à fila: {titulo}")

    except Exception as e:
        print(f"Erro ao ler CSV da Shopee: {e}")

async def enviar_shopee(context: ContextTypes.DEFAULT_TYPE):
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

# Ciclo de postagem
async def ciclo_postagem(context: ContextTypes.DEFAULT_TYPE):
    hora_atual = datetime.now(TZ).hour
    if 7 <= hora_atual <= 23 and auto_post_shopee:
        postar_shopee()
        await enviar_shopee(context)
    else:
        print("⏸️ Fora do horário de postagem ou automático pausado.")

# Comandos
async def comando_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    postar_shopee()
    await enviar_shopee(context)
    await update.message.reply_text("📂 Produto Shopee postado manualmente.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = context.job_queue.get_jobs_by_name("ciclo_postagem")
    if jobs:
        proxima_exec = jobs[0].next_t.astimezone(TZ).strftime("%H:%M")
    else:
        proxima_exec = "Não agendado"

    texto_status = (
        f"📊 **Status do Bot**\n"
        f"🛒 Shopee na fila: {len(fila_shopee)}\n"
        f"⏰ Horário atual: {datetime.now(TZ).strftime('%H:%M')}\n"
        f"⚙️ Postagem automática: {'✅ Ligada' if auto_post_shopee else '⏸️ Pausada'}\n"
        f"🕒 Próxima postagem: {proxima_exec}"
    )
    await update.message.reply_text(texto_status, parse_mode="Markdown")

async def stop_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global auto_post_shopee
    auto_post_shopee = False
    await update.message.reply_text("⏸️ Envio automático da Shopee pausado.")

async def play_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global auto_post_shopee
    auto_post_shopee = True
    await update.message.reply_text("▶️ Envio automático da Shopee retomado.")

# Main
def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("csv", comando_csv))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("stopcsv", stop_csv))
    application.add_handler(CommandHandler("playcsv", play_csv))

    application.job_queue.run_repeating(
        ciclo_postagem,
        interval=60*10,
        first=0,
        name="ciclo_postagem"
    )

    print("🤖 Bot iniciado e agendamento configurado.")
    application.run_polling()

if __name__ == "__main__":
    main()
