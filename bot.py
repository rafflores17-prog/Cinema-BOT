# ================= BOT DE CINEMA v3.9 (BUSCA INTELIGENTE) =================
import html
import requests
import random
import logging
import psycopg2
from urllib.parse import urlparse, quote
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ================= CONFIGURAÇÕES =================
TOKEN = "8158367501:AAFDh-On-TklycKt2aj9WxUvQjWvxrH_U-Y"
TMDB_API_KEY = "c90fb79a2f7d756a49bee848bce5f413"
DATABASE_URL = "postgresql://neondb_owner:npg_uc8fRtixQZ6U@ep-orange-band-anlv6zu6-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
CATEGORIAS = ["now_playing", "popular", "upcoming", "top_rated"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

# ================= DB =================
def get_db_connection():
    res = urlparse(DATABASE_URL)
    return psycopg2.connect(dbname=res.path[1:], user=res.username, password=res.password, host=res.hostname, port=res.port)

def setup_database():
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute('CREATE TABLE IF NOT EXISTS subscribed_chats (chat_id BIGINT PRIMARY KEY);')
        conn.commit(); cur.close(); conn.close()
    except: pass

def add_chat_to_db(chat_id):
    try:
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("INSERT INTO subscribed_chats (chat_id) VALUES (%s) ON CONFLICT (chat_id) DO NOTHING;", (chat_id,))
        conn.commit(); cur.close(); conn.close()
    except: pass

# ================= LOGICA DE BUSCA INTELIGENTE =================
def get_smart_search_links(title, is_tv=False):
    """Gera links de busca refinada para encontrar conteúdo na net."""
    query_online = quote(f"assistir {title} {'série' if is_tv else 'filme'} online dublado")
    query_torrent = quote(f"{title} {'série' if is_tv else 'filme'} download torrent dublado 1080p")
    
    # Usando o DuckDuckGo para busca limpa (menos anúncios que o Google direto)
    link_online = f"https://duckduckgo.com/?q={query_online}"
    link_torrent = f"https://duckduckgo.com/?q={query_torrent}"
    
    return link_online, link_torrent

# ================= TMDB =================
def make_tmdb_request(endpoint, params={}):
    base = "https://api.themoviedb.org/3"
    p = {"api_key": TMDB_API_KEY, "language": "pt-BR", **params}
    try:
        r = requests.get(f"{base}/{endpoint}", params=p, timeout=10)
        return r.json()
    except: return None

async def send_item_info(context, chat_id, item, is_tv=False):
    if not item: return
    iid = item.get("id")
    title = item.get("name") if is_tv else item.get("title")
    
    caption = (f"{'📺' if is_tv else '🎬'} <b>{html.escape(title)}</b>\n\n"
               f"⭐ {item.get('vote_average', 0):.1f}/10\n"
               f"📖 {item.get('overview', 'Sem sinopse')[:300]}...")
    
    link_online, link_torrent = get_smart_search_links(title, is_tv)
    
    keyboard = [
        [InlineKeyboardButton("🎬 Ver Trailer (YouTube)", callback_data=f"tr_{'tv' if is_tv else 'mv'}_{iid}")],
        [InlineKeyboardButton("🔍 Onde Assistir Online", url=link_online)],
        [InlineKeyboardButton("📥 Procurar Torrent", url=link_torrent)]
    ]
    
    post = item.get("poster_path")
    if post:
        await context.bot.send_photo(chat_id, f"{TMDB_IMAGE_BASE_URL}{post}", caption=caption, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await context.bot.send_message(chat_id, caption, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

# ================= HANDLERS =================
async def handle_text(update, context):
    text = update.message.text
    chat_id = update.effective_chat.id
    
    if text == '🎬 Filmes em Cartaz':
        d = make_tmdb_request("movie/now_playing", {"region": "BR"})
        for m in d.get('results', [])[:3]: await send_item_info(context, chat_id, m)
    elif text == '🌟 Populares':
        d = make_tmdb_request("movie/popular", {"region": "BR"})
        for m in d.get('results', [])[:3]: await send_item_info(context, chat_id, m)
    elif text == '📺 Séries Populares':
        d = make_tmdb_request("tv/popular")
        for s in d.get('results', [])[:3]: await send_item_info(context, chat_id, s, is_tv=True)
    elif text == '🎲 Sugestão Aleatória':
        cat = random.choice(CATEGORIAS)
        d = make_tmdb_request(f"movie/{cat}", {"page": random.randint(1, 5)})
        if d.get('results'): await send_item_info(context, chat_id, random.choice(d['results']))
    elif text == '🔍 Buscar Filme':
        await update.message.reply_text("Digite: /filme Nome do Filme")

async def callback_handler(update, context):
    query = update.callback_query; await query.answer()
    parts = query.data.split("_")
    if parts[0] == "tr":
        tipo, iid = parts[1], parts[2]
        path = f"tv/{iid}/videos" if tipo == "tv" else f"movie/{iid}/videos"
        d = make_tmdb_request(path)
        link = next((f"https://youtube.com/watch?v={v['key']}" for v in d.get('results', []) if v['type'] == 'Trailer'), None)
        await query.message.reply_text(f"🎥 Trailer: {link}" if link else "❌ Não encontrado no YouTube.")

async def start(update, context):
    add_chat_to_db(update.effective_chat.id)
    kb = [['🎬 Filmes em Cartaz', '🌟 Populares'], ['📺 Séries Populares', '🎲 Sugestão Aleatória'], ['🔍 Buscar Filme']]
    await update.message.reply_text("🎬 <b>CineSky V3.9 - Busca Inteligente</b>\n\nAgora os botões pesquisam o filme real para você!", parse_mode='HTML', reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

def main():
    setup_database()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler(['start', 'cinema'], start))
    app.add_handler(CommandHandler('filme', lambda u, c: send_item_info(c, u.effective_chat.id, make_tmdb_request("search/movie", {"query": " ".join(c.args)}).get('results', [None])[0]) if c.args else None))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.run_polling()

if __name__ == "__main__": main()
