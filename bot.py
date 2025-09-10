def buscar_promocoes():
    termo = random.choice(list(CATEGORIAS.keys()))
    emoji = CATEGORIAS[termo]
    print(f"🔍 Buscando por: {termo}")

    url_keyword = f"https://shopee.com.br/api/v4/search/search_items?by=relevancy&keyword={termo}&limit=20&newest=0&order=desc&page_type=search"

    try:
        r = requests.get(url_keyword, headers=HEADERS, timeout=15)
        data = r.json()
        promocoes = extrair_promocoes(data, emoji)

        if promocoes:
            return promocoes

        print("⚠️ Nenhum item por palavra-chave. Tentando fallback por categoria...")

        # Fallback por categoria ID
        categorias_fallback = {
            "moda": 110443,
            "eletronicos": 110429,
            "casa": 110444,
            "adulto": 110451
        }
        categoria_nome, categoria_id = random.choice(list(categorias_fallback.items()))
        emoji_fallback = {
            "moda": "👗",
            "eletronicos": "📱",
            "casa": "🏠",
            "adulto": "🔞"
        }.get(categoria_nome, "🛍️")

        print(f"🔁 Fallback: buscando por categoria {categoria_nome}")

        url_categoria = f"https://shopee.com.br/api/v4/search/search_items?by=pop&limit=20&match_id={categoria_id}&newest=0&order=desc&page_type=category"
        r2 = requests.get(url_categoria, headers=HEADERS, timeout=15)
        data2 = r2.json()
        promocoes_fallback = extrair_promocoes(data2, emoji_fallback)

        return promocoes_fallback

    except Exception as e:
        print("⚠️ Erro ao buscar promoções:", e)
        return []

def extrair_promocoes(data, emoji):
    promocoes = []
    for item in data.get("items", []):
        produto = item.get("item_basic")
        if produto:
            itemid = produto["itemid"]
            if itemid in CACHE:
                continue
            CACHE.add(itemid)
            promocoes.append({
                "titulo": f"{emoji} {produto['name']}",
                "link": f"https://shopee.com.br/product/{produto['shopid']}/{itemid}",
                "img": f"https://cf.shopee.com.br/file/{produto['image']}"
            })
    return promocoes
