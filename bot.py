# ================= BOT DE CINEMA v2.3 (Links Corrigidos) =================
import html
import requests
import random
import time
import threading
import json
import logging
import os
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ================= CONFIGURAÇÕES =================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")

if not TOKEN or not TMDB_API_KEY:
    print("ERRO CRÍTICO: As variáveis de ambiente TELEGRAM_TOKEN e TMDB_API_KEY não foram definidas!")
    exit()

# CORREÇÃO AQUI: URL sem formatação de markdown
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
SUBSCRIBED_FILE = "subscribed_chats.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

# ================= CARREGAMENTO DE DADOS =================
try:
    with open(SUBSCRIBED_FILE, "r", encoding="utf-8") as f:
        subscribed_chats = set(json.load(f))
except (FileNotFoundError, json.JSONDecodeError):
    subscribed_chats = set()

def salvar_chats():
    with open(SUBSCRIBED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(subscribed_chats), f)

# ================= LISTAS E DADOS =================
CATEGORIAS = ["now_playing", "popular", "upcoming", "top_rated"]
GENEROS = {
    28: "Ação", 12: "Aventura", 16: "Animação", 35: "Comédia", 80: "Crime", 99: "Documentário", 18: "Drama", 10751: "Família", 14: "Fantasia", 36: "História", 27: "Terror", 10402: "Música", 9648: "Mistério", 10749: "Romance", 878: "Ficção Científica", 10770: "Filme de TV", 53: "Thriller", 10752: "Guerra", 37: "Faroeste"
}
MENSAGENS_BOAS_VINDAS = ["🎉 Bem-vindo(a), {nome}! Que alegria ter você aqui!", "🌟 Olá {nome}! Seja muito bem-vindo(a) ao grupo!"]

def escape_html(text: str) -> str: return html.escape(text or "")
def cortar_texto(texto: str, limite: int = 350) -> str: return texto[:limite] + ("..." if len(texto) > limite else "")

def make_tmdb_request(endpoint, params):
    # CORREÇÃO AQUI: URL sem formatação de markdown
    base_url = "https://api.themoviedb.org/3"
    full_url = f"{base_url}/{endpoint}"
    default_params = {"api_key": TMDB_API_KEY, "language": "pt-BR"}
    all_params = {**default_params, **params}
    try:
        response = requests.get(full_url, params=all_params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro de conexão com TMDB: {e}")
        return None

def get_trailer_link(movie_id):
    data = make_tmdb_request(f"movie/{movie_id}/videos", {})
    if not data or not data.get("results"): return None
    videos = data["results"]
    for video in videos:
        if video["site"] == "YouTube" and video["type"] == "Trailer" and video.get("official"):
            # CORREÇÃO AQUI: URL sem formatação de markdown
            return f"https://www.youtube.com/watch?v={video['key']}"
    for video in videos:
        if video["site"] == "YouTube" and video["type"] == "Trailer":
            return f"https://www.youtube.com/watch?v={video['key']}"
    for video in videos:
        if video["site"] == "YouTube" and video["type"] == "Teaser":
            return f"https://www.youtube.com/watch?v={video['key']}"
    return None

def get_movies_by_category(category, limit=5):
    data = make_tmdb_request(f"movie/{category}", {"region": "BR", "page": 1})
    return data.get("results", [])[:limit] if data else []

def get_random_movie():
    category = random.choice(CATEGORIAS)
    data = make_tmdb_request(f"movie/{category}", {"region": "BR", "page": random.randint(1, 5)})
    return random.choice(data["results"]) if data and data.get("results") else None

def search_movie(query):
    data = make_tmdb_request("search/movie", {"query": query, "page": 1})
    return data.get("results", []) if data else []

def get_movies_by_genre(genre_id, limit=5):
    data = make_tmdb_request("discover/movie", {"with_genres": genre_id, "sort_by": "popularity.desc"})
    return data.get("results", [])[:limit] if data else []

def get_popular_series(limit=5):
    data = make_tmdb_request("tv/popular", {"page": 1})
    return data.get("results", [])[:limit] if data else []

def format_movie_message(movie):
    title = escape_html(movie.get("title", "Título desconhecido"))
    rating = movie.get("vote_average", 0)
    overview = cortar_texto(escape_html(movie.get("overview", "Sinopse não disponível.")))
    release_date = movie.get("release_date", "Data desconhecida")
    genre_ids = movie.get("genre_ids", [])
    genres_str = ", ".join([GENEROS.get(gid, "") for gid in genre_ids if gid in GENEROS]) or "N/A"
    stars = "⭐" * round(rating / 2) + "☆" * (5 - round(rating / 2))
    # CORREÇÃO AQUI: URL sem formatação de markdown
    return (f"🎬 <b>{title}</b>\n\n{stars} ({rating:.1f}/10)\n📅 <b>Lançamento:</b> {release_date}\n🎭 <b>Gêneros:</b> {genres_str}\n\n📖 <b>Sinopse:</b>\n{overview}\n\n🔗 https://www.themoviedb.org/movie/{movie.get('id', '')}")

def format_series_message(series):
    title = escape_html(series.get("name", "Título desconhecido"))
    rating = series.get("vote_average", 0)
    overview = cortar_texto(escape_html(series.get("overview", "Sinopse não disponível.")))
    first_air_date = series.get("first_air_date", "Data desconhecida")
    stars = "⭐" * round(rating / 2) + "☆" * (5 - round(rating / 2))
    # CORREÇÃO AQUI: URL sem formatação de markdown
    return (f"📺 <b>{title}</b>\n\n{stars} ({rating:.1f}/10)\n📅 <b>Estreia:</b> {first_air_date}\n\n📖 <b>Sinopse:</b>\n{overview}\n\n🔗 https://www.themoviedb.org/tv/{series.get('id', '')}")

async def send_movie_info(context: ContextTypes.DEFAULT_TYPE, chat_id: int, movie: dict):
    try:
        caption = format_movie_message(movie)
        poster_path = movie.get("poster_path")
        movie_id = movie.get("id")
        keyboard = [[InlineKeyboardButton("🎬 Ver Trailer", callback_data=f"trailer_{movie_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if poster_path:
            await context.bot.send_photo(chat_id, f"{TMDB_IMAGE_BASE_URL}{poster_path}", caption=caption, parse_mode='HTML', reply_markup=reply_markup)
        else:
            await context.bot.send_message(chat_id, caption, parse_mode='HTML', reply_markup=reply_markup)
    except Exception as e:
        logging.error(f"Erro ao enviar info de filme: {e}")

async def send_series_info(context: ContextTypes.DEFAULT_TYPE, chat_id: int, series: dict):
    try:
        caption = format_series_message(series)
        poster_path = series.get("poster_path")
        if poster_path:
            await context.bot.send_photo(chat_id, f"{TMDB_IMAGE_BASE_URL}{poster_path}", caption=caption, parse_mode='HTML')
        else:
            await context.bot.send_message(chat_id, caption, parse_mode='HTML')
    except Exception as e:
        logging.error(f"Erro ao enviar info de série: {e}")

async def start_cinema(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subscribed_chats.add(update.message.chat.id)
    salvar_chats()
    keyboard = [['🎬 Filmes em Cartaz', '🌟 Populares'], ['🚀 Em Breve', '🏆 Melhores Avaliados'],
                ['📺 Séries Populares', '🎲 Sugestão Aleatória'], ['🔍 Buscar Filme', '🎭 Por Gênero']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("🎬 <b>Bot de Cinema!</b>\n\nBem-vindo(a)! Use os botões para explorar.", parse_mode='HTML', reply_markup=reply_markup)

async def trailer_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() 
    movie_id = query.data.split('_')[1]
    trailer_link = get_trailer_link(movie_id)
    if trailer_link:
        await query.message.reply_text(f"Aqui está o trailer:\n{trailer_link}", disable_web_page_preview=False)
    else:
        await query.message.reply_text("Desculpe, não consegui encontrar um trailer para este filme.")

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for new_user in update.message.new_chat_members:
        nome = escape_html(new_user.first_name)
        msg = random.choice(MENSAGENS_BOAS_VINDAS).format(nome=nome)
        await update.message.reply_text(msg)

async def send_movie_list(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str, title: str):
    await update.message.reply_text(f"Buscando <b>{title}</b>...", parse_mode='HTML')
    movies = get_movies_by_category(category)
    if movies:
        for movie in movies:
            await send_movie_info(context, update.message.chat.id, movie)
            time.sleep(1)
    else:
        await update.message.reply_text(f"❌ Não foi possível encontrar filmes para {title}.")

async def lancamentos(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_movie_list(update, context, "now_playing", "Filmes em Cartaz")
async def populares(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_movie_list(update, context, "popular", "Filmes Populares")
async def em_breve(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_movie_list(update, context, "upcoming", "Filmes em Breve")
async def top_avaliados(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_movie_list(update, context, "top_rated", "Melhores Avaliados")
async def sugerir_filme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    movie = get_random_movie()
    if movie: await send_movie_info(context, update.message.chat.id, movie)
    else: await update.message.reply_text("❌ Nenhuma sugestão encontrada.")
async def series_populares(update: Update, context: ContextTypes.DEFAULT_TYPE):
    series_list = get_popular_series()
    if series_list:
        for s in series_list:
            await send_series_info(context, update.message.chat.id, s)
            time.sleep(1)
    else:
        await update.message.reply_text("❌ Não consegui buscar séries populares.")
async def prompt_buscar_filme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Use: <code>/filme [nome]</code>", parse_mode='HTML')
async def buscar_filme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Exemplo: <code>/filme Matrix</code>", parse_mode='HTML')
        return
    nome = " ".join(context.args)
    movies = search_movie(nome)
    if movies:
        await send_movie_info(context, update.message.chat.id, movies[0])
    else:
        await update.message.reply_text(f"❌ Nenhum filme chamado '{escape_html(nome)}'.")
async def listar_generos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lista = "\n".join([f"• {nome} (<code>{gid}</code>)" for gid, nome in GENEROS.items()])
    await update.message.reply_text(f"🎭 <b>Gêneros Disponíveis:</b>\n\n{lista}\n\nUse: <code>/genero [ID]</code>", parse_mode='HTML')
async def filmes_por_genero(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Exemplo: <code>/genero 28</code>", parse_mode='HTML')
        return
    try:
        gid = int(context.args[0])
        nome = GENEROS.get(gid)
        if not nome:
            await update.message.reply_text("❌ ID inválido. Veja /generos", parse_mode='HTML')
            return
        movies = get_movies_by_genre(gid)
        if movies:
            for movie in movies:
                await send_movie_info(context, update.message.chat.id, movie)
                time.sleep(1)
        else:
            await update.message.reply_text(f"❌ Nenhum filme de {nome}.")
    except (ValueError, IndexError):
        await update.message.reply_text("❌ ID deve ser número. Exemplo: /genero 28", parse_mode='HTML')

async def agendador_job(context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"Agendador a executar para {len(subscribed_chats)} chats.")
    for chat_id in list(subscribed_chats):
        try:
            suggestion = get_random_movie()
            if suggestion:
                await send_movie_info(context, chat_id, suggestion)
                time.sleep(1)
        except Exception as e:
            logging.error(f"Erro no agendador para o chat {chat_id}: {e}")
            if "Forbidden" in str(e) or "bot was blocked" in str(e):
                logging.info(f"A remover o chat {chat_id} por estar bloqueado.")
                subscribed_chats.discard(chat_id)
                salvar_chats()

def main():
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler(['start', 'cinema'], start_cinema))
    application.add_handler(CommandHandler('filme', buscar_filme))
    application.add_handler(CommandHandler('genero', filmes_por_genero))
    application.add_handler(MessageHandler(filters.Regex('^🎬 Filmes em Cartaz$'), lancamentos))
    application.add_handler(MessageHandler(filters.Regex('^🌟 Populares$'), populares))
    application.add_handler(MessageHandler(filters.Regex('^🚀 Em Breve$'), em_breve))
    application.add_handler(MessageHandler(filters.Regex('^🏆 Melhores Avaliados$'), top_avaliados))
    application.add_handler(MessageHandler(filters.Regex('^🎲 Sugestão Aleatória$'), sugerir_filme))
    application.add_handler(MessageHandler(filters.Regex('^📺 Séries Populares$'), series_populares))
    application.add_handler(MessageHandler(filters.Regex('^🔍 Buscar Filme$'), prompt_buscar_filme))
    application.add_handler(MessageHandler(filters.Regex('^🎭 Por Gênero$'), listar_generos))
    application.add_handler(CallbackQueryHandler(trailer_button_handler, pattern='^trailer_'))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    job_queue = application.job_queue
    job_queue.run_repeating(agendador_job, interval=10800, first=10)
    
    logging.info("🎬 A iniciar o Bot de Cinema (v2.3 com Links Corrigidos)...")
    application.run_polling()

if __name__ == "__main__":
    main()
