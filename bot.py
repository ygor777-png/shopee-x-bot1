import os
import pandas as pd
import random
import re
import pyshorteners
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import pytz
import requests
from urllib.parse import urlparse, parse_qs

# =========================
# Configurações
# =========================

# 🔹 Token do bot via variável de ambiente (Railway)
TOKEN = os.getenv("BOT_TOKEN")  # Configure BOT_TOKEN no Railway

# 🔹 URL do CSV online (opcional)
CSV_URLS = os.getenv("CSV_URLS")  # Configure CSV_URLS no Railway se quiser buscar online

# IDs dos grupos
GRUPO_ENTRADA_ML = -4653176769  # ID do grupo de entrada Mercado Livre
GRUPO_SAIDA_ID = -1001592474533    # ID do grupo de saída (promoções)

# Link central de redes sociais
LINK_CENTRAL = "https://atom.bio/ofertas_express"

# Timezone Brasil
TZ = pytz.timezone("America/Sao_Paulo")

# Filas de postagem
fila_shopee = []
fila_ml = []

# Controle de postagem automática Shopee
auto_post_shopee = True

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
        if CSV_URLS:
            print(f"📡 Lendo CSV da URL: {CSV_URLS}")
            df = pd.read_csv(CSV_URLS)
        else:
            print("📂 Lendo CSV local: produtos.csv")
            df = pd.read_csv("produtos.csv")

        if df.empty:
            return None

        # Escolhe linha aleatória e guarda índice antes de converter para dict
        linha_aleatoria = df.sample(n=1).iloc[0]
        indice = linha_aleatoria.name

        # Converte para dict
        row = linha_aleatoria.to_dict()

        # Remove essa linha do DataFrame
        df = df.drop(indice)

        # Se estiver usando local, atualiza o arquivo
        if not CSV_URLS:
            df.to_csv("produtos.csv", index=False)

        return row

    except Exception as e:
        print(f"Erro ao processar CSV: {e}")
        return None

async def postar_shopee():
    if not auto_post_shopee:
        print("⏸️ Postagem automática da Shopee está pausada.")
        return

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

import re

def extrair_link_de_mensagem(texto: str) -> str | None:
    match = re.search(r"https?://\S+", texto)
    if match:
        return match.group(0)
    return None

def resolver_url(link: str) -> str:
    try:
        resp = requests.head(link, allow_redirects=True, timeout=10)
        final_url = resp.url
        if final_url == link:
            resp_get = requests.get(link, allow_redirects=True, timeout=10)
            final_url = resp_get.url
        return final_url
    except Exception as e:
        print(f"⚠️ Falha ao resolver URL: {e}")
        return link

PADROES_ID = [
    r"/item/(ML[A-Z]\d+)",
    r"/p/(ML[A-Z]\d+)",
    r"/(ML[A-Z])[-_]?(\d+)",
]

def extrair_id_por_regex(url: str) -> str | None:
    for padrao in PADROES_ID:
        m = re.search(padrao, url, flags=re.IGNORECASE)
        if m:
            if len(m.groups()) == 2:
                return f"{m.group(1).upper()}{m.group(2)}"
            return m.group(1).upper()
    try:
        qs = parse_qs(urlparse(url).query)
        cand = qs.get("item_id", [None])[0]
        if cand and re.match(r"ML[A-Z]\d+", cand, flags=re.IGNORECASE):
            return cand.upper()
    except:
        pass
    return None

def termo_de_busca(url: str) -> str | None:
    try:
        qs = parse_qs(urlparse(url).query)
        for k in ["matt_word", "q", "query", "keyword"]:
            if k in qs and qs[k]:
                return qs[k][0].strip()
        path = urlparse(url).path
        segs = [s for s in path.split("/") if s]
        if "social" in segs:
            idx = segs.index("social")
            if idx + 1 < len(segs):
                return segs[idx + 1].strip()
    except:
        pass
    return None

def buscar_id_por_termo(termo: str) -> str | None:
    try:
        url_busca = f"https://api.mercadolibre.com/sites/MLB/search?q={requests.utils.quote(termo)}"
        r = requests.get(url_busca, timeout=10)
        if r.status_code == 200:
            data = r.json()
            results = data.get("results", [])
            for item in results:
                item_id = item.get("id")
                if item_id and re.match(r"ML[A-Z]\d+", item_id, flags=re.IGNORECASE):
                    return item_id.upper()
    except Exception as e:
        print(f"⚠️ Falha ao buscar por termo: {e}")
    return None

def extrair_id_ml(link: str) -> str | None:
    final_url = resolver_url(link)
    item_id = extrair_id_por_regex(final_url)
    if item_id:
        return item_id
    termo = termo_de_busca(final_url)
    if termo:
        item_id = buscar_id_por_termo(termo)
        if item_id:
            return item_id
    item_id = extrair_id_por_regex(link)
    if item_id:
        return item_id
    return None

async def capturar_ml(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (update.message.text or "").strip()
    link = extrair_link_de_mensagem(texto)
    if not link:
        await update.message.reply_text("⚠️ Nenhum link encontrado na mensagem.")
        return

    id_produto = extrair_id_ml(link)
    if not id_produto:
        await update.message.reply_text("⚠️ Não consegui identificar o ID do produto.")
        return

    try:
        r = requests.get(f"https://api.mercadolibre.com/items/{id_produto}", timeout=10)
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
        if not fila_shopee:
            print("Nenhum produto Shopee na fila para enviar.")
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
        if not fila_ml:
            print("Nenhum produto Mercado Livre na fila para enviar.")
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
        # Shopee sempre puxa do CSV e posta
        await postar_shopee()
        await enviar_shopee(context)


# 🚀 Boas-vindas
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Olá! Seja bem-vindo ao bot.\n"
        "Use /comandos para ver tudo o que posso fazer."
    )

# 📋 Lista de comandos
async def comando_lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comandos_texto = """
📋 **Lista de Comandos do Bot**

🚀 **/start** — Dá as boas-vindas e explica como o bot funciona.

📂 **/csv** — Força leitura imediata do CSV da Shopee e posta o próximo produto.

📊 **/status** — Mostra o status atual do bot:
   • Quantos produtos estão na fila da Shopee.
   • Quantos produtos estão na fila do Mercado Livre.
   • Horário atual.
   • Se a postagem automática está ligada.
   • Horário da próxima postagem.

⏸️ **/stopcsv** — Pausa o envio automático da Shopee.

▶️ **/playcsv** — Retoma o envio automático da Shopee.

📋 **/comandos** — Mostra esta lista de comandos.
"""
    await update.message.reply_text(comandos_texto, parse_mode="Markdown")

# 📂 Força leitura CSV Shopee
async def comando_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await postar_shopee()
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
        f"📊 **Status do Bot**\n"
        f"🛒 Shopee na fila: {len(fila_shopee)}\n"
        f"📦 Mercado Livre na fila: {len(fila_ml)}\n"
        f"⏰ Horário atual: {datetime.now(TZ).strftime('%H:%M')}\n"
        f"⚙️ Postagem automática: {'✅ Ligada' if auto_post_shopee else '⏸️ Pausada'}\n"
        f"🕒 Próxima postagem: {proxima_exec}"
    )
    await update.message.reply_text(texto_status, parse_mode="Markdown")

# ⏸️ Pausa Shopee
async def stop_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global auto_post_shopee
    auto_post_shopee = False
    await update.message.reply_text("⏸️ Envio automático da Shopee pausado.")

# ▶️ Retoma Shopee
async def play_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global auto_post_shopee
    auto_post_shopee = True
    await update.message.reply_text("▶️ Envio automático da Shopee retomado.")


# Função principal
def main():
    application = Application.builder().token(TOKEN).build()

    # 🎯 COMANDOS PRINCIPAIS
    application.add_handler(CommandHandler("start", start))       
    application.add_handler(CommandHandler("comandos", comando_lista))  
    application.add_handler(CommandHandler("csv", comando_csv))   
    application.add_handler(CommandHandler("status", status))     
    application.add_handler(CommandHandler("stopcsv", stop_csv))  
    application.add_handler(CommandHandler("playcsv", play_csv))  

    # 📦 Captura manual Mercado Livre
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, capturar_ml))

    # ⏱️ Agendamento único a cada 10 minutos
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
