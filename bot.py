# ================= BOT DE CINEMA v3.8 (FIX LINKS & TORRENT) =================
import html
import requests
import random
import time
import logging
import psycopg2
from urllib.parse import urlparse
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ================= CONFIGURAÇÕES =================
TOKEN = "8158367501:AAFDh-On-TklycKt2aj9WxUvQjWvxrH_U-Y"
TMDB_API_KEY = "c90fb79a2f7d756a49bee848bce5f413"
DATABASE_URL = "postgresql://neondb_owner:npg_uc8fRtixQZ6U@ep-orange-band-anlv6zu6-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
CATEGORIAS = ["now_playing", "popular", "upcoming", "top_rated"]
GENEROS = {28: "Ação", 12: "Aventura", 16: "Animação", 35: "Comédia", 80: "Crime", 99: "Documentário", 18: "Drama", 10751: "Família", 14: "Fantasia", 36: "História", 27: "Terror", 10402: "Música", 9648: "Mistério", 10749: "Romance", 878: "Ficção Científica", 10770: "Filme de TV", 53: "Thriller", 10752: "Guerra", 37: "Faroeste"}

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

# ================= LINKS =================
def get_stream_link(tmdb_id, is_tv=False):
    # SuperEmbed é mais estável para visualização mobile
    if is_tv:
        return f"https://multiembed.mov/?video_id={tmdb_id}&tmdb=1"
    return f"https://superembed.xyz/movie/{tmdb_id}"

def get_torrent_magnet(title):
    try:
        # Limpa o título para melhorar a busca
        clean_title = "".join(c for c in title if c.isalnum() or c==' ')
        q = requests.utils.quote(clean_title)
        url = f"https://yts.mx/api/v2/list_movies.json?query_term={q}&limit=1"
        res = requests.get(url, timeout=10).json()
        if res.get('data', {}).get('movie_count', 0) > 0:
            movie = res['data']['movies'][0]
            hash_code = movie['torrents'][0]['hash']
            return f"magnet:?xt=urn:btih:{hash_code}&dn={q}"
    except: return None
    return None

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
    
    keyboard = [
        [InlineKeyboardButton("🎬 Ver Trailer", callback_data=f"trailer_{'tv' if is_tv else 'mv'}_{iid}")],
        [InlineKeyboardButton("📺 Assistir Online", url=get_stream_link(iid, is_tv))]
    ]
    
    if not is_tv:
        keyboard[1].append(InlineKeyboardButton("📥 Torrent", callback_data=f"torrent_{iid}"))
    
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
    elif text == '🚀 Em Breve':
        d = make_tmdb_request("movie/upcoming", {"region": "BR"})
        for m in d.get('results', [])[:3]: await send_item_info(context, chat_id, m)
    elif text == '🏆 Melhores Avaliados':
        d = make_tmdb_request("movie/top_rated", {"region": "BR"})
        for m in d.get('results', [])[:3]: await send_item_info(context, chat_id, m)
    elif text == '📺 Séries Populares':
        d = make_tmdb_request("tv/popular")
        for s in d.get('results', [])[:3]: await send_item_info(context, chat_id, s, is_tv=True)
    elif text == '🎲 Sugestão Aleatória':
        cat = random.choice(CATEGORIAS)
        d = make_tmdb_request(f"movie/{cat}", {"page": random.randint(1, 5)})
        if d.get('results'): await send_item_info(context, chat_id, random.choice(d['results']))
    elif text == '🎭 Por Gênero':
        lista = "\n".join([f"• {n} (<code>{g}</code>)" for g, n in GENEROS.items()])
        await update.message.reply_text(f"🎭 <b>Gêneros:</b>\n\n{lista}\n\nUse: /genero [ID]", parse_mode='HTML')
    elif text == '🔍 Buscar Filme':
        await update.message.reply_text("Digite: /filme Nome do Filme")

async def callback_handler(update, context):
    query = update.callback_query; await query.answer()
    parts = query.data.split("_")
    if parts[0] == "trailer":
        tipo, iid = parts[1], parts[2]
        path = f"tv/{iid}/videos" if tipo == "tv" else f"movie/{iid}/videos"
        d = make_tmdb_request(path)
        link = next((f"https://youtube.com/watch?v={v['key']}" for v in d.get('results', []) if v['type'] == 'Trailer'), None)
        await query.message.reply_text(f"🎥 Trailer: {link}" if link else "❌ Não encontrado.")
    elif parts[0] == "torrent":
        movie = make_tmdb_request(f"movie/{parts[1]}")
        magnet = get_torrent_magnet(movie.get('title'))
        if magnet: await query.message.reply_text(f"📥 <b>Magnet Link:</b>\n\n<code>{magnet}</code>", parse_mode='HTML')
        else: await query.message.reply_text("❌ Não encontrei torrents ativos (YTS) para este filme.")

async def start(update, context):
    add_chat_to_db(update.effective_chat.id)
    kb = [['🎬 Filmes em Cartaz', '🌟 Populares'], ['🚀 Em Breve', '🏆 Melhores Avaliados'], 
          ['📺 Séries Populares', '🎲 Sugestão Aleatória'], ['🔍 Buscar Filme', '🎭 Por Gênero']]
    await update.message.reply_text("🎬 <b>CineSky V3.8 Ativado!</b>", parse_mode='HTML', reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

def main():
    setup_database()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler(['start', 'cinema'], start))
    app.add_handler(CommandHandler('filme', lambda u, c: send_item_info(c, u.effective_chat.id, make_tmdb_request("search/movie", {"query": " ".join(c.args)}).get('results', [None])[0]) if c.args else None))
    app.add_handler(CommandHandler('genero', lambda u, c: [send_item_info(c, u.effective_chat.id, m) for m in make_tmdb_request("discover/movie", {"with_genres": c.args[0]}).get('results', [])[:3]] if c.args else None))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.run_polling()

if __name__ == "__main__": main()
