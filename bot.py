# ================= BOT DE CINEMA v4.8 (CINE MEGA EXCLUSIVE) =================
import html
import os
import requests
import random
import logging
import psycopg2
from urllib.parse import urlparse, quote
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ================= CONFIGURAÇÕES (via variáveis de ambiente) =================
TOKEN = os.environ.get("TOKEN", "")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
SITE_URL = os.environ.get("SITE_URL", "https://streamflix-app-iota.vercel.app")
APP_URL = os.environ.get("APP_URL", "http://bgdv.online/ed7g1w")

# ID do grupo e tópico
GRUPO_ID = int(os.environ.get("GRUPO_ID", "-1003177664821"))
TOPIC_ID = int(os.environ.get("TOPIC_ID", "4342"))

GENEROS_MENU = {
    "🔥 Ação": 28,
    "🤡 Comédia": 35,
    "👻 Terror": 27,
    "🛸 Ficção": 878,
    "🕵️ Suspense": 53,
    "🧸 Animação": 16,
}

EPOCAS_MENU = {
    "🎸 Anos 80": (1980, 1989),
    "💾 Anos 90": (1990, 1999),
    "💿 Anos 2000": (2000, 2010),
    "🆕 Recentes": (2020, 2026),
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s"
)
logger = logging.getLogger(__name__)

# ================= VALIDAÇÃO DE STARTUP =================
def validar_config():
    """Valida se as variáveis obrigatórias estão configuradas."""
    erros = []
    if not TOKEN:
        erros.append("TOKEN")
    if not TMDB_API_KEY:
        erros.append("TMDB_API_KEY")
    if not DATABASE_URL:
        erros.append("DATABASE_URL")
    if erros:
        raise EnvironmentError(
            f"❌ Variáveis de ambiente não definidas: {', '.join(erros)}\n"
            "Configure-as no Koyeb em Settings > Environment Variables."
        )

# ================= BANCO DE DADOS =================
def get_db_connection():
    """Cria conexão com o banco de dados PostgreSQL."""
    res = urlparse(DATABASE_URL)
    return psycopg2.connect(
        dbname=res.path[1:],
        user=res.username,
        password=res.password,
        host=res.hostname,
        port=res.port,
        sslmode="require",
        connect_timeout=10,
    )

def setup_database():
    """Cria as tabelas necessárias se não existirem."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS subscribed_chats "
            "(chat_id BIGINT PRIMARY KEY);"
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.info("✅ Banco de dados inicializado com sucesso.")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar banco de dados: {e}")

def add_chat_to_db(chat_id: int):
    """Adiciona um chat ao banco de dados de inscritos."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO subscribed_chats (chat_id) VALUES (%s) "
            "ON CONFLICT (chat_id) DO NOTHING;",
            (chat_id,)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Erro ao adicionar chat ao DB: {e}")

def get_all_chats():
    """Retorna todos os chats cadastrados."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT chat_id FROM subscribed_chats")
        chats = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return chats
    except Exception as e:
        logger.error(f"Erro ao buscar chats: {e}")
        return []

# ================= TMDB =================
def make_tmdb_request(endpoint: str, params: dict = {}) -> dict | None:
    """Faz uma requisição à API do TMDB com tratamento de erros."""
    base = "https://api.themoviedb.org/3"
    p = {"api_key": TMDB_API_KEY, "language": "pt-BR", **params}
    try:
        r = requests.get(f"{base}/{endpoint}", params=p, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout na requisição TMDB: {endpoint}")
    except requests.exceptions.HTTPError as e:
        logger.warning(f"Erro HTTP TMDB {endpoint}: {e}")
    except Exception as e:
        logger.error(f"Erro inesperado TMDB {endpoint}: {e}")
    return None

def buscar_trailer(item_id: int, titulo: str, is_tv: bool = False) -> str:
    """Busca o trailer no TMDB ou gera link de busca no YouTube."""
    tipo = "tv" if is_tv else "movie"
    v = make_tmdb_request(f"{tipo}/{item_id}/videos")
    if v and v.get("results"):
        videos = v["results"]
        trailer = next(
            (vid for vid in videos if vid["type"] == "Trailer" and vid["site"] == "YouTube"),
            None
        )
        if not trailer:
            trailer = next((vid for vid in videos if vid["site"] == "YouTube"), None)
        if trailer:
            return f"https://youtube.com/watch?v={trailer['key']}"

    busca_query = quote(f"{titulo} Trailer Oficial Português")
    return f"https://www.youtube.com/results?search_query={busca_query}"

# ================= ENVIO NO TÓPICO =================
async def enviar_no_topico(
    context: ContextTypes.DEFAULT_TYPE,
    text: str = None,
    photo: str = None,
    caption: str = None,
    reply_markup=None,
    parse_mode: str = "HTML",
):
    """Envia mensagem sempre no tópico configurado do grupo."""
    kwargs = {"parse_mode": parse_mode}

    if TOPIC_ID:
        kwargs["message_thread_id"] = TOPIC_ID
    if reply_markup:
        kwargs["reply_markup"] = reply_markup

    try:
        if photo:
            return await context.bot.send_photo(
                GRUPO_ID, photo, caption=caption, **kwargs
            )
        elif text:
            return await context.bot.send_message(GRUPO_ID, text, **kwargs)
    except Exception as e:
        logger.error(f"Erro ao enviar no tópico {TOPIC_ID}: {e}")

async def send_item_info(
    context: ContextTypes.DEFAULT_TYPE,
    item: dict,
    is_tv: bool = False,
):
    """Monta e envia as informações de um filme ou série."""
    if not item:
        return

    iid = item.get("id")
    title = item.get("name") if is_tv else item.get("title")
    if not title:
        return

    rating = item.get("vote_average", 0)
    stars = "⭐" * round(rating / 2)
    overview = item.get("overview") or "Sinopse não disponível."
    overview_resumida = overview[:280] + ("..." if len(overview) > 280 else "")

    caption = (
        f"{'📺' if is_tv else '🎬'} <b>{html.escape(title)}</b>\n\n"
        f"{stars} ({rating:.1f}/10)\n"
        f"📖 {overview_resumida}"
    )

    trailer_url = buscar_trailer(iid, title, is_tv)
    titulo_url = quote(title)
    link_filme = f"{SITE_URL}/search?q={titulo_url}"

    keyboard = [
        [InlineKeyboardButton("▶ ASSISTIR AGORA", url=link_filme)],
        [InlineKeyboardButton("💬 BAIXAR APP AQUI", url=APP_URL)],
    ]
    markup = InlineKeyboardMarkup(keyboard)
    post = item.get("poster_path")

    try:
        if post:
            await enviar_no_topico(
                context,
                photo=f"{TMDB_IMAGE_BASE_URL}{post}",
                caption=caption,
                reply_markup=markup,
            )
        else:
            await enviar_no_topico(context, text=caption, reply_markup=markup)

        if trailer_url:
            await enviar_no_topico(
                context,
                text=f"🎥 <b>Confira o Trailer:</b>\n{trailer_url}",
            )
    except Exception as e:
        logger.error(f"Erro ao enviar informações do item '{title}': {e}")

# ================= HANDLERS DE TEXTO =================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa mensagens de texto recebidas no grupo."""
    if not update.message or not update.message.text:
        return

    # Só responde no grupo configurado
    if update.effective_chat.id != GRUPO_ID:
        return

    text = update.message.text

    if text == "🎥 Em Cartaz":
        d = make_tmdb_request("movie/now_playing", {"region": "BR"})
        if d:
            for m in d.get("results", [])[:3]:
                await send_item_info(context, m)

    elif text == "🚀 Em Breve":
        d = make_tmdb_request("movie/upcoming", {"region": "BR"})
        if d:
            for m in d.get("results", [])[:3]:
                await send_item_info(context, m)

    elif text == "🌟 Populares":
        d = make_tmdb_request("movie/popular", {"region": "BR"})
        if d:
            for m in d.get("results", [])[:3]:
                await send_item_info(context, m)

    elif text == "📺 Séries":
        d = make_tmdb_request("tv/popular")
        if d:
            for s in d.get("results", [])[:3]:
                await send_item_info(context, s, is_tv=True)

    elif text == "🎭 Por Gênero":
        btns = [
            [InlineKeyboardButton(n, callback_data=f"gen_{i}")]
            for n, i in GENEROS_MENU.items()
        ]
        await enviar_no_topico(
            context,
            text="✨ <b>Escolha um Gênero:</b>",
            reply_markup=InlineKeyboardMarkup(btns),
        )

    elif text == "🎞️ Por Época":
        btns = [
            [InlineKeyboardButton(n, callback_data=f"era_{n}")]
            for n in EPOCAS_MENU.keys()
        ]
        await enviar_no_topico(
            context,
            text="⏳ <b>Escolha uma Época:</b>",
            reply_markup=InlineKeyboardMarkup(btns),
        )

    elif text == "🎲 Sugestão":
        d = make_tmdb_request("movie/top_rated", {"page": random.randint(1, 20)})
        if d and d.get("results"):
            await send_item_info(context, random.choice(d["results"]))

    elif text == "🔍 Buscar":
        await enviar_no_topico(
            context,
            text="⌨️ Digite: <code>/filme Nome do Filme</code>",
        )

# ================= CALLBACKS =================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa callbacks dos botões inline."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("gen_"):
        gid = data.split("_")[1]
        d = make_tmdb_request(
            "discover/movie",
            {"with_genres": gid, "page": random.randint(1, 5)},
        )
        if d and d.get("results"):
            filmes = d["results"]
            random.shuffle(filmes)
            for m in filmes[:3]:
                await send_item_info(context, m)

    elif data.startswith("era_"):
        # O nome da época pode conter "_", então juntamos de volta
        era_nome = "_".join(data.split("_")[1:])
        if era_nome not in EPOCAS_MENU:
            return
        inicio, fim = EPOCAS_MENU[era_nome]
        ano_sorteado = random.randint(inicio, fim)
        d = make_tmdb_request(
            "discover/movie",
            {
                "primary_release_year": ano_sorteado,
                "sort_by": "popularity.desc",
                "page": 1,
            },
        )
        if d and d.get("results"):
            await enviar_no_topico(
                context,
                text=f"🎞️ <b>Buscando os melhores de {ano_sorteado}...</b>",
            )
            filmes = d["results"][:10]
            random.shuffle(filmes)
            for m in filmes[:3]:
                await send_item_info(context, m)

# ================= COMANDOS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start — apresenta o bot e o menu principal."""
    add_chat_to_db(update.effective_chat.id)
    user = update.effective_user

    kb = [
        ["🎥 Em Cartaz", "🚀 Em Breve"],
        ["🌟 Populares", "📺 Séries"],
        ["🎭 Por Gênero", "🎞️ Por Época"],
        ["🎲 Sugestão", "🔍 Buscar"],
    ]

    promo_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 ACESSAR SITE OFICIAL", url=SITE_URL)],
        [InlineKeyboardButton("💬 BAIXAR APP AQUI", url=APP_URL)],
    ])

    await enviar_no_topico(
        context,
        text=(
            f"🎬 <b>CineSky v4.8 - Cine Mega</b>\n\n"
            f"Olá {html.escape(user.first_name)}! "
            f"Tudo pronto para sua sessão de cinema hoje? 🍿"
        ),
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
    )
    await enviar_no_topico(
        context,
        text="Acesse nosso site oficial para assistir agora:",
        reply_markup=promo_kb,
    )

async def buscar_filme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /filme <nome> — busca um filme pelo nome."""
    if not context.args:
        await enviar_no_topico(
            context,
            text="⚠️ Use: <code>/filme Nome do Filme</code>",
        )
        return

    nome = " ".join(context.args)
    d = make_tmdb_request("search/movie", {"query": nome})
    if not d or not d.get("results"):
        await enviar_no_topico(
            context,
            text=f"❌ Nenhum resultado encontrado para: <b>{html.escape(nome)}</b>",
        )
        return

    await send_item_info(context, d["results"][0])

async def avisogeral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /avisogeral <mensagem> — envia aviso para todos os chats inscritos."""
    if not context.args:
        await update.message.reply_text("⚠️ Use: /avisogeral Sua mensagem aqui")
        return

    msg = " ".join(context.args)
    chats = get_all_chats()
    enviados = 0

    for chat_id in chats:
        try:
            await context.bot.send_message(chat_id, msg, parse_mode="HTML")
            enviados += 1
        except Exception as e:
            logger.warning(f"Erro ao enviar aviso para {chat_id}: {e}")

    await update.message.reply_text(
        f"📢 Aviso enviado para {enviados}/{len(chats)} chats!"
    )

# ================= MAIN =================
def main():
    """Inicializa e executa o bot."""
    validar_config()
    setup_database()

    application = Application.builder().token(TOKEN).build()

    # Registro de handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("filme", buscar_filme))
    application.add_handler(CommandHandler("avisogeral", avisogeral))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )
    application.add_handler(CallbackQueryHandler(callback_handler))

    logger.info(f"✅ Bot Online | Site: {SITE_URL} | Grupo: {GRUPO_ID} | Tópico: {TOPIC_ID}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
