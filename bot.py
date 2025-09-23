import os
import re
import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# 🔹 Configurações
TOKEN = os.getenv("BOT_TOKEN")  # Token do bot
GRUPO_SAIDA_ID = int(os.getenv("GRUPO_SAIDA_ID", "-1001592474533"))  # ID do grupo de saída
CSV_URLS = os.getenv("CSV_URLS", "")  # URL do CSV da Shopee (opcional)
LINK_CENTRAL = os.getenv("LINK_CENTRAL", "https://atom.bio/ofertas_express")  # Link central

# 🔹 Fila de produtos
fila_shopee = []
fila_ml = []

# 🔹 Controle de postagem automática
auto_post_shopee = True

# 🔹 Fuso horário
import pytz
TZ = pytz.timezone("America/Sao_Paulo")

def achar(row, *keys):
    """Procura o primeiro campo existente na linha do CSV."""
    for key in keys:
        if key in row and pd.notna(row[key]):
            return str(row[key]).strip()
    return None

def formatar_preco(valor):
    """Formata preço para R$X,XX."""
    try:
        valor = str(valor).replace(",", ".")
        return f"R${float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return valor

def encurtar_link(link):
    """Encurta link usando TinyURL."""
    try:
        r = requests.get(f"http://tinyurl.com/api-create.php?url={link}", timeout=10)
        if r.status_code == 200:
            return r.text
    except:
        pass
    return link

def criar_anuncio(link, titulo, precos):
    """Cria texto do anúncio Shopee."""
    precos_txt = " ➡ ".join(precos) if precos else ""
    return f"""⚡ EXPRESS ACHOU, CONFIRA! ⚡

{titulo}

💰 {precos_txt}

👉 Compre por aqui: {link}

⚠️ Corre que acaba rápido!

🌐 Siga nossas redes sociais:
{LINK_CENTRAL}"""

def postar_shopee():
    """Lê o CSV da Shopee e adiciona o próximo produto à fila."""
    try:
        if not CSV_URLS:
            print("⚠️ Nenhuma URL de CSV configurada.")
            return

        print(f"Lendo CSV da URL: {CSV_URLS}")
        df = pd.read_csv(CSV_URLS)

        for _, row in df.iterrows():
            titulo = achar(row, "Product Name", "Título", "title")
            preco1 = achar(row, "price", "old_price", "preco_original", "original_price", "preço original")
            preco2 = achar(row, "preco", "sale_price", "valor", "current_price", "preço atual")
            link = achar(row, "link", "url", "product_link", "produto_url", "url do produto")

            if not titulo or not link:
                continue

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
            break  # adiciona apenas o primeiro produto novo

    except Exception as e:
        print(f"Erro ao ler CSV da Shopee: {e}")

def postar_shopee():
    """Lê o CSV da Shopee e adiciona o próximo produto à fila."""
    try:
        if not CSV_URLS:
            print("⚠️ Nenhuma URL de CSV configurada.")
            return

        print(f"Lendo CSV da URL: {CSV_URLS}")
        df = pd.read_csv(CSV_URLS)

        for _, row in df.iterrows():
            titulo = achar(row, "Product Name", "Título", "title")
            preco1 = achar(row, "Price", "Preço", "price")
            preco2 = achar(row, "Discount Price", "Preço com desconto", "discount_price")
            link = achar(row, "Link", "URL", "link")

            if not titulo or not link:
                continue

            link_encurtado = encurtar_link(link)
            precos = []
            if preco1:
                precos.append(formatar_preco(preco1))
            if preco2 and preco2 != preco1:
                precos.append(formatar_preco(preco2))

            anuncio = criar_anuncio(link_encurtado, titulo, precos)
            imagem = achar(row, "Image", "Imagem", "image")

            fila_shopee.append({
                "titulo": titulo,
                "imagem": imagem,
                "anuncio": anuncio
            })
            print(f"✅ Produto Shopee adicionado à fila: {titulo}")
            break  # adiciona apenas o primeiro produto novo

    except Exception as e:
        print(f"Erro ao ler CSV da Shopee: {e}")

import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

def extrair_link_de_mensagem(texto: str) -> str | None:
    match = re.search(r"https?://\S+", texto)
    if match:
        return match.group(0)
    return None

def resolver_url(link: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(link, headers=headers, allow_redirects=True, timeout=15)
        return resp.url
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

def extrair_id_por_html(link: str) -> str | None:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(link, headers=headers, timeout=15)
        m = re.search(r"MLB\d{6,}", resp.text)
        if m:
            return m.group(0)
    except Exception as e:
        print(f"⚠️ Falha ao extrair ID do HTML: {e}")
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
    item_id = extrair_id_por_html(final_url)
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
    item_id = extrair_id_por_html(link)
    if item_id:
        return item_id
    return None

def extrair_dados_html(link_produto: str) -> dict:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(link_produto, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        titulo_tag = soup.find("h1")
        titulo = titulo_tag.get_text(strip=True) if titulo_tag else "Produto sem título"

        preco_tag = soup.find("span", {"class": re.compile(r"price-tag-fraction")})
        preco = preco_tag.get_text(strip=True) if preco_tag else ""

        imagem_tag = soup.find("img", {"class": re.compile(r"ui-pdp-image")})
        imagem = imagem_tag["src"] if imagem_tag and "src" in imagem_tag.attrs else ""

        return {"titulo": titulo, "preco": preco, "imagem": imagem}
    except Exception as e:
        print(f"⚠️ Falha ao extrair dados HTML: {e}")
        return {"titulo": "", "preco": "", "imagem": ""}

async def capturar_ml(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (update.message.text or "").strip()
    link_afiliado = extrair_link_de_mensagem(texto)
    if not link_afiliado:
        await update.message.reply_text("⚠️ Nenhum link encontrado na mensagem.")
        return

    id_produto = extrair_id_ml(link_afiliado)
    if not id_produto:
        await update.message.reply_text("⚠️ Não consegui identificar o ID do produto.")
        return

    link_produto = f"https://produto.mercadolivre.com.br/{id_produto}"
    dados = extrair_dados_html(link_produto)

    titulo = dados["titulo"]
    preco = formatar_preco(dados["preco"]) if dados["preco"] else "Preço indisponível"
    imagem = dados["imagem"]

    link_encurtado = encurtar_link(link_afiliado)

    anuncio = f"""⚡ EXPRESS ACHOU, CONFIRA! ⚡

{titulo}

💰 Por: {preco}
📦 Oferta exclusiva

👉 Compre por aqui: {link_encurtado}

⚠️ Corre que acaba rápido!

🌐 Siga nossas redes sociais:
{LINK_CENTRAL}"""

    fila_ml.append({"titulo": titulo, "imagem": imagem, "anuncio": anuncio})
    await update.message.reply_text("✅ Produto do Mercado Livre adicionado à fila.")

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
