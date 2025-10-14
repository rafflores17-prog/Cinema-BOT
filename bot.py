# ================= BOT DE CINEMA MELHORADO E SEGURO =================
import html
import requests
import telebot
import random
import time
import threading
import json
import logging
import os

# ================= CONFIGURAÇÕES =================
# As chaves secretas agora são lidas das variáveis de ambiente do Railway
TOKEN = os.environ.get("TELEGRAM_TOKEN")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")

if not TOKEN or not TMDB_API_KEY:
    print("ERRO CRÍTICO: As variáveis de ambiente TELEGRAM_TOKEN e TMDB_API_KEY não foram definidas!")
    exit()

TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
SUBSCRIBED_FILE = "subscribed_chats.json"

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler()] # No Railway, é melhor usar StreamHandler para ver os logs no painel
)

# ================= BOT PRINCIPAL =================
bot = telebot.TeleBot(TOKEN)

# ================= VARIÁVEIS GLOBAIS =================
if os.path.exists(SUBSCRIBED_FILE):
    try:
        with open(SUBSCRIBED_FILE, "r", encoding="utf-8") as f:
            subscribed_chats = set(json.load(f))
    except (json.JSONDecodeError, FileNotFoundError):
        subscribed_chats = set()
else:
    subscribed_chats = set()

def salvar_chats():
    with open(SUBSCRIBED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(subscribed_chats), f)

# (O resto do seu código, com toda a lógica de filmes, continua aqui... nada foi alterado)
# ================= LISTAS E CONFIGURAÇÕES =================
CATEGORIAS = ["now_playing", "popular", "upcoming", "top_rated"]
GENEROS = {
    28: "Ação", 12: "Aventura", 16: "Animação", 35: "Comédia",
    80: "Crime", 99: "Documentário", 18: "Drama", 10751: "Família",
    14: "Fantasia", 36: "História", 27: "Terror", 10402: "Música",
    9648: "Mistério", 10749: "Romance", 878: "Ficção Científica",
    10770: "Filme de TV", 53: "Thriller", 10752: "Guerra", 37: "Faroeste"
}
MENSAGENS_BOAS_VINDAS = [
    "🎉 Bem-vindo(a), {nome}! Que alegria ter você aqui!",
    "🌟 Olá {nome}! Seja muito bem-vindo(a) ao grupo!",
]

# ================= FUNÇÕES DE SEGURANÇA =================
def escape_html(text: str) -> str:
    return html.escape(text or "")

def cortar_texto(texto: str, limite: int = 350) -> str:
    return texto[:limite] + ("..." if len(texto) > limite else "")

# ================= FUNÇÕES DE API =================
def make_tmdb_request(endpoint, params):
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

# ================= FUNÇÕES DE FORMATAÇÃO =================
def format_movie_message(movie):
    title = escape_html(movie.get("title", "Título desconhecido"))
    rating = movie.get("vote_average", 0)
    overview = cortar_texto(escape_html(movie.get("overview", "Sinopse não disponível.")))
    release_date = movie.get("release_date", "Data desconhecida")
    genre_ids = movie.get("genre_ids", [])
    genres_str = ", ".join([GENEROS.get(gid, "") for gid in genre_ids if gid in GENEROS]) or "N/A"
    stars = "⭐" * round(rating / 2) + "☆" * (5 - round(rating / 2))
    return (
        f"🎬 <b>{title}</b>\n\n"
        f"{stars} ({rating:.1f}/10)\n"
        f"📅 <b>Lançamento:</b> {release_date}\n"
        f"🎭 <b>Gêneros:</b> {genres_str}\n\n"
        f"📖 <b>Sinopse:</b>\n{overview}\n\n"
        f"🔗 https://www.themoviedb.org/movie/{movie.get('id', '')}"
    )

def format_series_message(series):
    title = escape_html(series.get("name", "Título desconhecido"))
    rating = series.get("vote_average", 0)
    overview = cortar_texto(escape_html(series.get("overview", "Sinopse não disponível.")))
    first_air_date = series.get("first_air_date", "Data desconhecida")
    stars = "⭐" * round(rating / 2) + "☆" * (5 - round(rating / 2))
    return (
        f"📺 <b>{title}</b>\n\n"
        f"{stars} ({rating:.1f}/10)\n"
        f"📅 <b>Estreia:</b> {first_air_date}\n\n"
        f"📖 <b>Sinopse:</b>\n{overview}\n\n"
        f"🔗 https://www.themoviedb.org/tv/{series.get('id', '')}"
    )

def send_movie_info(chat_id, movie):
    try:
        caption = format_movie_message(movie)
        poster_path = movie.get("poster_path")
        if poster_path:
            bot.send_photo(chat_id, f"{TMDB_IMAGE_BASE_URL}{poster_path}", caption=caption, parse_mode='HTML')
        else:
            bot.send_message(chat_id, caption, parse_mode='HTML')
    except Exception as e:
        logging.error(f"Erro ao enviar info de filme: {e}")

def send_series_info(chat_id, series):
    try:
        caption = format_series_message(series)
        poster_path = series.get("poster_path")
        if poster_path:
            bot.send_photo(chat_id, f"{TMDB_IMAGE_BASE_URL}{poster_path}", caption=caption, parse_mode='HTML')
        else:
            bot.send_message(chat_id, caption, parse_mode='HTML')
    except Exception as e:
        logging.error(f"Erro ao enviar info de série: {e}")

# ================= AGENDADOR =================
def agendador_cinema():
    while True:
        time.sleep(10800)  # 3h
        logging.info(f"Agendador rodando para {len(subscribed_chats)} chats.")
        for chat_id in list(subscribed_chats):
            try:
                suggestion = get_random_movie()
                if suggestion:
                    send_movie_info(chat_id, suggestion)
                    time.sleep(1)
            except Exception as e:
                logging.error(f"Erro no agendador para chat {chat_id}: {e}")
                if "Forbidden" in str(e) or "bot was blocked" in str(e):
                    logging.info(f"Removendo chat {chat_id} por estar bloqueado.")
                    subscribed_chats.discard(chat_id)
                    salvar_chats()

# ================= COMANDOS =================
@bot.message_handler(commands=['start', 'cinema'])
def start_cinema(message):
    subscribed_chats.add(message.chat.id)
    salvar_chats()
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('🎬 Filmes em Cartaz', '🌟 Populares', '🚀 Em Breve', '🏆 Melhores Avaliados',
               '📺 Séries Populares', '🎲 Sugestão Aleatória', '🔍 Buscar Filme', '🎭 Por Gênero')
    bot.send_message(message.chat.id, "🎬 <b>Bot de Cinema!</b>\n\nBem-vindo(a)! Use os botões para explorar.",
                     parse_mode='HTML', reply_markup=markup)

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    for new_user in message.new_chat_members:
        nome = escape_html(new_user.first_name)
        msg = random.choice(MENSAGENS_BOAS_VINDAS).format(nome=nome)
        bot.send_message(message.chat.id, msg)

def send_movie_list(message, category, title):
    bot.send_message(message.chat.id, f"Buscando <b>{title}</b>...", parse_mode='HTML')
    movies = get_movies_by_category(category)
    if movies:
        for movie in movies:
            send_movie_info(message.chat.id, movie)
            time.sleep(1)
    else:
        bot.send_message(message.chat.id, f"❌ Não foi possível encontrar filmes para {title}.")

# Handlers de categorias
@bot.message_handler(regexp="🎬 Filmes em Cartaz")
def lancamentos(message): send_movie_list(message, "now_playing", "Filmes em Cartaz")
@bot.message_handler(regexp="🌟 Populares")
def populares(message): send_movie_list(message, "popular", "Filmes Populares")
@bot.message_handler(regexp="🚀 Em Breve")
def em_breve(message): send_movie_list(message, "upcoming", "Filmes em Breve")
@bot.message_handler(regexp="🏆 Melhores Avaliados")
def top_avaliados(message): send_movie_list(message, "top_rated", "Melhores Avaliados")
@bot.message_handler(regexp="🎲 Sugestão Aleatória")
def sugerir_filme(message):
    movie = get_random_movie()
    if movie: send_movie_info(message.chat.id, movie)
    else: bot.send_message(message.chat.id, "❌ Nenhuma sugestão encontrada.")

@bot.message_handler(regexp="📺 Séries Populares")
def series_populares(message):
    series_list = get_popular_series()
    if series_list:
        for s in series_list:
            send_series_info(message.chat.id, s)
            time.sleep(1)
    else:
        bot.send_message(message.chat.id, "❌ Não consegui buscar séries populares.")

@bot.message_handler(regexp="🔍 Buscar Filme")
def prompt_buscar_filme(message):
    bot.send_message(message.chat.id, "Use: <code>/filme [nome]</code>", parse_mode='HTML')

@bot.message_handler(commands=['filme'])
def buscar_filme(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Exemplo: <code>/filme Matrix</code>", parse_mode='HTML')
        return
    nome = args[1]
    movies = search_movie(nome)
    if movies:
        send_movie_info(message.chat.id, movies[0])
    else:
        bot.send_message(message.chat.id, f"❌ Nenhum filme chamado '{escape_html(nome)}'.")

@bot.message_handler(regexp="🎭 Por Gênero")
def listar_generos(message):
    lista = "\n".join([f"• {nome} (<code>{gid}</code>)" for gid, nome in GENEROS.items()])
    bot.send_message(message.chat.id,
                     f"🎭 <b>Gêneros Disponíveis:</b>\n\n{lista}\n\nUse: <code>/genero [ID]</code>",
                     parse_mode='HTML')

@bot.message_handler(commands=['genero'])
def filmes_por_genero(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Exemplo: <code>/genero 28</code>", parse_mode='HTML')
        return
    try:
        gid = int(args[1])
        nome = GENEROS.get(gid)
        if not nome:
            bot.reply_to(message, "❌ ID inválido. Veja /generos", parse_mode='HTML')
            return
        movies = get_movies_by_genre(gid)
        if movies:
            for movie in movies:
                send_movie_info(message.chat.id, movie)
                time.sleep(1)
        else:
            bot.send_message(message.chat.id, f"❌ Nenhum filme de {nome}.")
    except ValueError:
        bot.reply_to(message, "❌ ID deve ser número. Exemplo: /genero 28", parse_mode='HTML')

# ================= INICIALIZAÇÃO =================
if __name__ == "__main__":
    logging.info("🎬 Iniciando Bot de Cinema (versão segura)...")
    threading.Thread(target=agendador_cinema, daemon=True).start()
    logging.info("⏰ Agendador ativado.")
    bot.infinity_polling(skip_pending=True, timeout=20)


