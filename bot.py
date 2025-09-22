import pandas as pd
import random
import re
import pyshorteners
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import pytz
import requests

# Configurações
TOKEN = "SEU_TOKEN_AQUI"
GRUPO_ENTRADA_ML = -1001234567890  # ID do grupo de entrada Mercado Livre
GRUPO_SAIDA_ID = -1009876543210    # ID do grupo de saída (promoções)
LINK_CENTRAL = "https://seusite.com/redes"

# Timezone Brasil
TZ = pytz.timezone("America/Sao_Paulo")

# Filas de postagem
fila_shopee = []
fila_ml = []

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
    return f"""⚡ EXPRESS ACHOU, CONFIRA! ⚡

{titulo}

{texto_preco}

👉 Compre por aqui: {link}

⚠️ Corre que acaba rápido!

🌐 Siga nossas redes sociais:
{LINK_CENTRAL}"""

def processar_csv():
    try:
        df = pd.read_csv("produtos.csv")
        if df.empty:
            return None
        # Pega o primeiro produto e remove da lista
        row = df.iloc[0].to_dict()
        df = df.drop(df.index[0])
        df.to_csv("produtos.csv", index=False)
        return row
    except Exception as e:
        print(f"Erro ao processar CSV: {e}")
        return None

async def postar_shopee():
    hora_atual = datetime.now(TZ).hour
    if hora_atual < 7 or hora_atual >= 23:
        print("⏸️ Fora do horário de postagem automática (Shopee).")
        return

    row = processar_csv()
    if not row:
        print("Nenhum produto Shopee disponível.")
        return

    link_produto = achar(row, "link", "url", "product_link", "produto_url", "url do produto")
    titulo_original = achar(row, "titulo", "title", "name", "produto", "product_name", "nome")
    preco_atual = achar(row, "preco", "sale_price", "valor", "current_price", "preço atual")
    preco_antigo = achar(row, "price", "old_price", "preco_original", "original_price", "preço original")
    imagem_url = achar(row, "imagem", "image_link", "img_url", "foto", "picture")

    precos = []
    if preco_atual:
        precos.append(formatar_preco(preco_atual))
    if preco_antigo:
        precos.insert(0, formatar_preco(preco_antigo))

    anuncio = criar_anuncio(encurtar_link(link_produto), titulo_original, precos)

    fila_shopee.append({"titulo": titulo_original, "imagem": imagem_url, "anuncio": anuncio})
    print(f"✅ Produto Shopee adicionado à fila: {titulo_original}")

def extrair_id_ml(link):
    try:
        if "/item/" in link:
            return link.split("/item/")[1].split("?")[0]
        elif "/p/" in link:
            return link.split("/p/")[1].split("?")[0]
        elif "/social/" in link:
            return link.split("/social/")[1].split("?")[0]
    except:
        return None
    return None

async def capturar_ml(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GRUPO_ENTRADA_ML:
        return

    link = update.message.text.strip()
    id_produto = extrair_id_ml(link)
    if not id_produto:
        await update.message.reply_text("⚠️ Não consegui identificar o ID do produto.")
        return

    try:
        r = requests.get(f"https://api.mercadolibre.com/items/{id_produto}")
        if r.status_code != 200:
            await update.message.reply_text("❌ Erro ao buscar produto no Mercado Livre.")
            return
        dados = r.json()

        titulo = dados.get("title", "Produto sem título")
        preco = formatar_preco(dados.get("price", ""))
        parcelas = dados.get("installments", {})
        if parcelas:
            qtd = parcelas.get("quantity", 0)
            valor_parcela = parcelas.get("amount", 0)
            juros = parcelas.get("rate", 0)
            if juros == 0:
                info_parcelas = f"{qtd}x de {formatar_preco(valor_parcela)} sem juros"
            else:
                info_parcelas = f"{qtd}x de {formatar_preco(valor_parcela)} com juros"
        else:
            info_parcelas = "Sem informação de parcelamento"

        frete_tags = dados.get("shipping", {}).get("tags", [])
        frete_info = "🚚 Frete Full" if "fulfillment" in frete_tags else "📦 Frete normal"

        imagem = dados.get("thumbnail", "")
        anuncio = f"""⚡ EXPRESS ACHOU, CONFIRA! ⚡

{titulo}

💰 Por: {preco}
💳 {info_parcelas}
{frete_info}

👉 Compre por aqui: {link}

⚠️ Corre que acaba rápido!

🌐 Siga nossas redes sociais:
{LINK_CENTRAL}"""

        fila_ml.append({"titulo": titulo, "imagem": imagem, "anuncio": anuncio})
        await update.message.reply_text("✅ Produto do Mercado Livre adicionado à fila.")

    except Exception as e:
        await update.message.reply_text(f"Erro: {e}")

async def enviar_shopee(context: ContextTypes.DEFAULT_TYPE):
    try:
        hora_atual = datetime.now(TZ).hour
        if hora_atual < 7 or hora_atual >= 23:
            print("⏸️ Fora do horário de postagem automática (Shopee).")
            return

        if not fila_shopee:
            print("Nenhum produto Shopee na fila.")
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
        print(f"✅ Shopee enviado: {produto['titulo']}")

    except Exception as e:
        print(f"Erro ao enviar Shopee: {e}")


async def enviar_ml(context: ContextTypes.DEFAULT_TYPE):
    try:
        hora_atual = datetime.now(TZ).hour
        if hora_atual < 7 or hora_atual >= 23:
            print("⏸️ Fora do horário de postagem automática (Mercado Livre).")
            return

        if not fila_ml:
            print("Nenhum produto Mercado Livre na fila.")
            return

        produto = fila_ml.pop(0)
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
        print(f"✅ Mercado Livre enviado: {produto['titulo']}")

    except Exception as e:
        print(f"Erro ao enviar Mercado Livre: {e}")

async def ciclo_postagem(context: ContextTypes.DEFAULT_TYPE):
    # Se houver produto do Mercado Livre na fila, ele tem prioridade
    if fila_ml:
        await enviar_ml(context)
    else:
        await enviar_shopee(context)


async def comando_lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comandos_texto = """
📋 **Lista de Comandos do Bot**

🚀 **/start** — Dá as boas-vindas e explica como o bot funciona.

📂 **/csv** — Força leitura imediata do CSV da Shopee e posta o próximo produto.

📊 **/status** — Mostra o status atual do bot:
   • Quantos produtos estão na fila da Shopee.
   • Quantos produtos estão na fila do Mercado Livre.
   • Horário atual.

⏸️ **/stopcsv** — Pausa o envio automático da Shopee.

▶️ **/playcsv** — Retoma o envio automático da Shopee.

📋 **/comandos** — Mostra esta lista de comandos.

💡 **Como funciona o Mercado Livre**:
   • Envie o link de afiliado (pode ser encurtado) no grupo de entrada.
   • O bot busca imagem, preço, parcelas, frete e cupom.
   • O produto entra na fila e será postado no próximo ciclo de 10 minutos.

⚡ **Ciclo de Postagem**:
   • A cada 10 minutos, das 07h às 23h.
   • Se houver produto do Mercado Livre na fila, ele tem prioridade.
   • Caso contrário, posta Shopee.
"""
    await update.message.reply_text(comandos_texto, parse_mode="Markdown")


def main():
    application = Application.builder().token(TOKEN).build()

    # 🎯 COMANDOS PRINCIPAIS
    application.add_handler(CommandHandler("start", start))       # 🚀 Boas-vindas
    application.add_handler(CommandHandler("comandos", comando_lista))  # 📋 Lista de comandos
    application.add_handler(CommandHandler("csv", comando_csv))   # 📂 Força leitura CSV Shopee
    application.add_handler(CommandHandler("status", status))     # 📊 Status do bot
    application.add_handler(CommandHandler("stopcsv", stop_csv))  # ⏸️ Pausa Shopee
    application.add_handler(CommandHandler("playcsv", play_csv))  # ▶️ Retoma Shopee

    # 📦 Captura manual Mercado Livre
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, capturar_ml))

    # ⏱️ Agendamento único a cada 10 minutos
    application.job_queue.run_repeating(
        ciclo_postagem,
        interval=60*10,
        first=0
    )

    print("🤖 Bot iniciado e agendamento configurado.")
    application.run_polling()
