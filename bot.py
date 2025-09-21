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
    return t[:500]  # suporta até ~150 palavras

def _fallback_titulo_local(titulo_original: str) -> str:
    palavras = titulo_original.split()
    if not palavras:
        return "Oferta imperdível para você"
    if len(palavras) > 12:
        return " ".join(palavras[:12]) + "..."
    return titulo_original

def gerar_titulo_descontraido_ia(titulo_original):
    try:
        if not HF_TOKEN:
            print("❌ HF_TOKEN não configurado.")
            return _fallback_titulo_local(titulo_original)

        url = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        payload = {
            "inputs": (
                "Crie um título chamativo (máx. 150 palavras) para este produto, "
                "em português do Brasil, sem emojis, sem repetir o título original, "
                "e que desperte interesse de compra. "
                f"Título original: {titulo_original}\n"
                "Responda apenas com o título."
            ),
            "parameters": {"max_new_tokens": 300, "temperature": 0.8, "do_sample": True}
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            print(f"❌ Erro HF {resp.status_code}: {resp.text}")
            return _fallback_titulo_local(titulo_original)

        data = resp.json()
        print(f"🔍 Resposta HF: {data}")

        texto = ""
        if isinstance(data, list) and "generated_text" in data[0]:
            texto = data[0]["generated_text"]
        elif isinstance(data, dict) and "generated_text" in data:
            texto = data["generated_text"]

        if not texto.strip():
            print("⚠️ Hugging Face retornou resposta vazia.")
            return _fallback_titulo_local(titulo_original)

        linha_curta = _sanitizar_linha(texto)
        return linha_curta if linha_curta else _fallback_titulo_local(titulo_original)

    except Exception as e:
        print(f"❌ Erro Hugging Face: {type(e).__name__} - {e}")
        return _fallback_titulo_local(titulo_original)

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
            # Converte para o fuso horário configurado
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
        row = processar_csv()
        if row is None:
            print("Nenhum produto para enviar.")
            return

        # Extrai dados do CSV usando a função achar
        link_produto = achar(row, "link", "url", "product_link", "produto_url", "url do produto")
        titulo_original = achar(row, "titulo", "title", "name", "produto", "product_name", "nome")
        preco_atual = achar(row, "preco", "sale_price", "valor", "current_price", "preço atual")
        preco_antigo = achar(row, "price", "old_price", "preco_original", "original_price", "preço original")
        imagem_url = achar(row, "image_link", "锘縤mage_link", "img_urll", "foto", "picture")

        # Monta lista de preços
        precos = []
        if preco_atual:
            precos.append(formatar_preco(preco_atual))
        if preco_antigo:
            precos.insert(0, formatar_preco(preco_antigo))

        # Gera título descontraído com IA (ou fallback local)
        titulo_curto = gerar_titulo_descontraido_ia(titulo_original)

        # Encurta link se válido
        link_encurtado = encurtar_link(link_produto)

        # Monta anúncio
        anuncio = criar_anuncio(link_encurtado, titulo_curto, precos)

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

        print(f"✅ Produto enviado: {titulo_curto}")

    except Exception as e:
        print(f"Erro ao enviar produto: {e}")

def main():
    application = Application.builder().token(TOKEN).build()

    # Comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("comandos", comando_lista))
    application.add_handler(CommandHandler("csv", comando_csv))
    application.add_handler(CommandHandler("status", status))

    # Inicia agendamento automático
    application.job_queue.run_repeating(
        enviar_produto,
        interval=60*60*4,  # a cada 4 horas
        first=0
    )

    print("🤖 Bot iniciado e agendamento configurado.")
    application.run_polling()

if __name__ == "__main__":
    main()
