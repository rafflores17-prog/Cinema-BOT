# ================= BOT DE CINEMA v3.7 (VERSÃO COMPLETA CORRIGIDA) =================
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

# ================= BANCO DE DADOS =================
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

# ================= FUNÇÕES DE BUSCA TMDB =================
def make_tmdb_request(endpoint, params={}):
    base = "https://api.themoviedb.org/3"
    p = {"api_key": TMDB_API_KEY, "language": "pt-BR", **params}
    try:
        r = requests.get(f"{base}/{endpoint}", params=p, timeout=10)
        return r.json()
    except: return None

# ================= LINKS EXTERNOS =================
def get_stream_link(tmdb_id, is_tv=False):
    tipo = "tv" if is_tv else "filme"
    return f"https://embed.warezcdn.net/{tipo}/{tmdb_id}"

def get_torrent_magnet(title):
    try:
        q = requests.utils.quote(title)
        url = f"https://yts.mx/api/v2/list_movies.json?query_term={q}&limit=1"
        res = requests.get(url, timeout=10).json()
        if res.get('data', {}).get('movie_count', 0) > 0:
            movie = res['data']['movies'][0]
            return f"magnet:?xt=urn:btih:{movie['torrents'][0]['hash']}&dn={q}"
    except: return None
    return None

# ================= ENVIO DE CONTEÚDO =================
async def send_item_info(context, chat_id, item, is_tv=False):
    if not item: return
    iid = item.get("id")
    title = item.get("name") if is_tv else item.get("title")
    caption = (f"{'📺' if is_tv else '🎬'} <b>{html.escape(title)}</b>\n\n"
               f"⭐ {item.get('vote_average', 0):.1f}/10\n"
               f"📖 {item.get('overview', 'Sem sinopse')[:300]}...")
    
    keyboard = [[InlineKeyboardButton("🎬 Ver Trailer", callback_data=f"trailer_{'tv' if is_tv else 'mv'}_{iid}")]]
    keyboard.append([InlineKeyboardButton("📺 Assistir Online", url=get_stream_link(iid, is_tv))])
    
    if not is_tv:
        keyboard[1].append(InlineKeyboardButton("📥 Torrent", callback_data=f"torrent_{iid}"))
    
    post = item.get("poster_path")
    reply_markup = InlineKeyboardMarkup(keyboard)
    if post:
        await context.bot.send_photo(chat_id, f"{TMDB_IMAGE_BASE_URL}{post}", caption=caption, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id, caption, parse_mode='HTML', reply_markup=reply_markup)

# ================= HANDLERS =================
async def handle_text(update, context):
    text = update.message.text
    chat_id = update.effective_chat.id
    
    if text == '🎬 Filmes em Cartaz':
        data = make_tmdb_request("movie/now_playing", {"region": "BR"})
        for m in data.get('results', [])[:3]: await send_item_info(context, chat_id, m)
    elif text == '🌟 Populares':
        data = make_tmdb_request("movie/popular", {"region": "BR"})
        for m in data.get('results', [])[:3]: await send_item_info(context, chat_id, m)
    elif text == '🚀 Em Breve':
        data = make_tmdb_request("movie/upcoming", {"region": "BR"})
        for m in data.get('results', [])[:3]: await send_item_info(context, chat_id, m)
    elif text == '🏆 Melhores Avaliados':
        data = make_tmdb_request("movie/top_rated", {"region": "BR"})
        for m in data.get('results', [])[:3]: await send_item_info(context, chat_id, m)
    elif text == '📺 Séries Populares':
        data = make_tmdb_request("tv/popular")
        for s in data.get('results', [])[:3]: await send_item_info(context, chat_id, s, is_tv=True)
    elif text == '🎲 Sugestão Aleatória':
        cat = random.choice(CATEGORIAS)
        data = make_tmdb_request(f"movie/{cat}", {"page": random.randint(1, 5)})
        if data.get('results'): await send_item_info(context, chat_id, random.choice(data['results']))
    elif text == '🎭 Por Gênero':
        lista = "\n".join([f"• {n} (<code>{g}</code>)" for g, n in GENEROS.items()])
        await update.message.reply_text(f"🎭 <b>Gêneros:</b>\n\n{lista}\n\nUse: /genero [ID]", parse_mode='HTML')
    elif text == '🔍 Buscar Filme':
        await update.message.reply_text("Digite: /filme Nome do Filme")

async def callback_handler(update, context):
    query = update.callback_query; await query.answer()
    parts = query.data.split("_")
    action = parts[0]
    
    if action == "trailer":
        tipo, iid = parts[1], parts[2]
        path = f"tv/{iid}/videos" if tipo == "tv" else f"movie/{iid}/videos"
        d = make_tmdb_request(path)
        link = next((f"https://youtube.com/watch?v={v['key']}" for v in d.get('results', []) if v['type'] == 'Trailer'), None)
        await query.message.reply_text(f"🎥 Trailer: {link}" if link else "❌ Não encontrado.")
    
    elif action == "torrent":
        movie = make_tmdb_request(f"movie/{parts[1]}")
        magnet = get_torrent_magnet(movie.get('title'))
        if magnet: await query.message.reply_text(f"📥 <b>Magnet Link:</b>\n\n<code>{magnet}</code>", parse_mode='HTML')
        else: await query.message.reply_text("❌ Torrent não encontrado.")

async def start(update, context):
    add_chat_to_db(update.effective_chat.id)
    kb = [['🎬 Filmes em Cartaz', '🌟 Populares'], ['🚀 Em Breve', '🏆 Melhores Avaliados'], 
          ['📺 Séries Populares', '🎲 Sugestão Aleatória'], ['🔍 Buscar Filme', '🎭 Por Gênero']]
    await update.message.reply_text("🎬 <b>CineSky V3.7 Ativado!</b>", parse_mode='HTML', reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

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
