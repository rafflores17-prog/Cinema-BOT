# ================= BOT DE CINEMA v3.5 (com Stream e Torrent) =================
import html
import requests
import random
import time
import threading
import json
import logging
import os
import psycopg2
from urllib.parse import urlparse
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ================= CONFIGURAÇÕES =================
TOKEN = "8158367501:AAFDh-On-TklycKt2aj9WxUvQjWvxrH_U-Y"
TMDB_API_KEY = "c90fb79a2f7d756a49bee848bce5f413"
DATABASE_URL = "postgresql://neondb_owner:npg_uc8fRtixQZ6U@ep-orange-band-anlv6zu6-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

if not all([TOKEN, TMDB_API_KEY, DATABASE_URL]):
    print("ERRO CRÍTICO: Verifique as chaves fixadas!")
    exit()

TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

# ================= FUNÇÕES DO BANCO DE DADOS =================
def get_db_connection():
    result = urlparse(DATABASE_URL)
    return psycopg2.connect(
        dbname=result.path[1:], user=result.username,
        password=result.password, host=result.hostname, port=result.port
    )

def setup_database():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS subscribed_chats (chat_id BIGINT PRIMARY KEY);')
    conn.commit()
    cur.close()
    conn.close()

def add_chat_to_db(chat_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO subscribed_chats (chat_id) VALUES (%s) ON CONFLICT (chat_id) DO NOTHING;", (chat_id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e: logging.error(f"Erro DB: {e}")

def get_all_chats_from_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT chat_id FROM subscribed_chats;")
        chats = [item[0] for item in cur.fetchall()]
        cur.close()
        conn.close()
        return chats
    except Exception as e: return []

def remove_chat_from_db(chat_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM subscribed_chats WHERE chat_id = %s;", (chat_id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e: logging.error(f"Erro DB: {e}")

# ================= FUNÇÕES DE BUSCA (STREAM E TORRENT) =================

def get_stream_link(tmdb_id):
    """Retorna link de player online (Embed)."""
    return f"https://embed.warezcdn.net/filme/{tmdb_id}"

def get_torrent_magnet(movie_title):
    """Busca um Magnet Link básico via API do YTS (Filmes de alta qualidade)."""
    try:
        url = f"https://yts.mx/api/v2/list_movies.json?query_term={movie_title}&limit=1"
        res = requests.get(url, timeout=10).json()
        if res['data']['movie_count'] > 0:
            movie = res['data']['movies'][0]
            hash_code = movie['torrents'][0]['hash']
            magnet = f"magnet:?xt=urn:btih:{hash_code}&dn={movie_title}"
            return magnet
    except: return None
    return None

# ================= LÓGICA DO BOT =================
CATEGORIAS = ["now_playing", "popular", "upcoming", "top_rated"]
GENEROS = {28: "Ação", 12: "Aventura", 16: "Animação", 35: "Comédia", 80: "Crime", 99: "Documentário", 18: "Drama", 10751: "Família", 14: "Fantasia", 36: "História", 27: "Terror", 10402: "Música", 9648: "Mistério", 10749: "Romance", 878: "Ficção Científica", 10770: "Filme de TV", 53: "Thriller", 10752: "Guerra", 37: "Faroeste"}
MENSAGENS_BOAS_VINDAS = ["🎉 Bem-vindo(a), {nome}! Que alegria ter você aqui!", "🌟 Olá {nome}! Seja muito bem-vindo(a) ao grupo!"]

def escape_html(text: str) -> str: return html.escape(text or "")
def cortar_texto(texto: str, limite: int = 350) -> str: return texto[:limite] + ("..." if len(texto) > limite else "")

def make_tmdb_request(endpoint, params):
    base_url = "https://api.themoviedb.org/3"
    default_params = {"api_key": TMDB_API_KEY, "language": "pt-BR"}
    try:
        response = requests.get(f"{base_url}/{endpoint}", params={**default_params, **params}, timeout=10)
        return response.json()
    except: return None

def get_trailer_link(movie_id):
    data = make_tmdb_request(f"movie/{movie_id}/videos", {})
    if not data or not data.get("results"): return None
    for v in data["results"]:
        if v["site"] == "YouTube" and v["type"] == "Trailer":
            return f"https://www.youtube.com/watch?v={v['key']}"
    return None

async def send_movie_info(context: ContextTypes.DEFAULT_TYPE, chat_id: int, movie: dict):
    try:
        movie_id = movie.get("id")
        title = movie.get("title", "Sem título")
        caption = (f"🎬 <b>{escape_html(title)}</b>\n\n"
                   f"⭐ {movie.get('vote_average', 0):.1f}/10\n"
                   f"📅 <b>Lançamento:</b> {movie.get('release_date', 'N/A')}\n\n"
                   f"📖 <b>Sinopse:</b>\n{cortar_texto(escape_html(movie.get('overview', '')))}")
        
        # Criação dos Botões Inline
        keyboard = [
            [InlineKeyboardButton("🎬 Ver Trailer", callback_data=f"trailer_{movie_id}")],
            [
                InlineKeyboardButton("📺 Assistir Online", url=get_stream_link(movie_id)),
                InlineKeyboardButton("📥 Baixar Torrent", callback_data=f"torrent_{movie_id}")
            ]
        ]
        
        poster_path = movie.get("poster_path")
        if poster_path:
            await context.bot.send_photo(chat_id, f"{TMDB_IMAGE_BASE_URL}{poster_path}", caption=caption, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await context.bot.send_message(chat_id, caption, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e: logging.error(f"Erro envio: {e}")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data.startswith("trailer_"):
        mid = data.split("_")[1]
        link = get_trailer_link(mid)
        msg = f"🎥 Aqui está o trailer:\n{link}" if link else "❌ Trailer não encontrado."
        await query.message.reply_text(msg)
    
    elif data.startswith("torrent_"):
        mid = data.split("_")[1]
        movie = make_tmdb_request(f"movie/{mid}", {})
        magnet = get_torrent_magnet(movie.get('title'))
        if magnet:
            await query.message.reply_text(f"📥 <b>Magnet Link Encontrado!</b>\n\nCopie e cole no seu app de Torrent:\n\n<code>{magnet}</code>", parse_mode='HTML')
        else:
            await query.message.reply_text("❌ Não encontrei torrents ativos para este filme no momento.")

# ================= COMANDOS E MAIN =================
async def start_cinema(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_chat_to_db(update.message.chat.id)
    kb = [['🎬 Filmes em Cartaz', '🌟 Populares'], ['🚀 Em Breve', '🏆 Melhores Avaliados'], ['🎲 Sugestão Aleatória', '🔍 Buscar Filme']]
    await update.message.reply_text("🎬 <b>Bem-vindo ao CineSky!</b>", parse_mode='HTML', reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def buscar_filme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else None
    if not query: return await update.message.reply_text("Use: /filme Nome do Filme")
    res = make_tmdb_request("search/movie", {"query": query})
    if res and res.get("results"): await send_movie_info(context, update.message.chat.id, res["results"][0])
    else: await update.message.reply_text("❌ Filme não encontrado.")

async def agendador_job(context: ContextTypes.DEFAULT_TYPE):
    for cid in get_all_chats_from_db():
        try:
            m = make_tmdb_request(f"movie/{random.choice(CATEGORIAS)}", {"region": "BR"})
            if m: await send_movie_info(context, cid, random.choice(m['results']))
        except: pass

def main():
    setup_database()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler(['start', 'cinema'], start_cinema))
    app.add_handler(CommandHandler('filme', buscar_filme))
    app.add_handler(MessageHandler(filters.Regex('^🎬 Filmes em Cartaz$'), lambda u, c: send_movie_list(u, c, "now_playing")))
    app.add_handler(MessageHandler(filters.Regex('^🌟 Populares$'), lambda u, c: send_movie_list(u, c, "popular")))
    app.add_handler(MessageHandler(filters.Regex('^🎲 Sugestão Aleatória$'), lambda u, c: send_movie_info(context, update.message.chat.id, get_random_movie())))
    app.add_handler(CallbackQueryHandler(callback_handler))
    
    app.job_queue.run_repeating(agendador_job, interval=10800, first=10)
    app.run_polling()

async def send_movie_list(update, context, cat):
    res = make_tmdb_request(f"movie/{cat}", {"region": "BR"})
    if res:
        for m in res['results'][:3]:
            await send_movie_info(context, update.message.chat.id, m)
            time.sleep(1)

if __name__ == "__main__": main()
