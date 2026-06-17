# ================= BOT DE CINEMA v5.0 (CINE MEGA EXCLUSIVE) =================
import os
import html
import time
import random
import logging
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, quote

import requests
import psycopg2
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ================= CONFIGURAÇÕES (USE VARIÁVEIS DE AMBIENTE NO ZEABUR!) =================
# IMPORTANTE: o TOKEN e a senha do banco abaixo ficaram expostos.
# Recomendo fortemente revogar/regenerar ambos e colocar os novos valores
# como variáveis de ambiente no painel do Zeabur (aba "Variable"),
# em vez de deixá-los escritos no código.
TOKEN = os.environ.get("BOT_TOKEN", "8158367501:AAEpU5YkliLbY9xddHohmbW6wTffM1ye49U")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "c90fb79a2f7d756a49bee848bce5f413")
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_uc8fRtixQZ6U@ep-orange-band-anlv6zu6-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require",
)

TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
SITE_URL = os.environ.get("SITE_URL", "https://streamflix-app-iota.vercel.app")
APP_URL = os.environ.get("APP_URL", "http://bgdv.online/ed7g1w")

GRUPO_ID = int(os.environ.get("GRUPO_ID", "-1003177664821"))
TOPIC_ID = int(os.environ.get("TOPIC_ID", "4342"))

# Quantos dias até um item poder ser repetido para o mesmo grupo
DIAS_SEM_REPETIR = 21

GENEROS_MENU = {
    "🔥 Ação": 28, "🤡 Comédia": 35, "👻 Terror": 27, "🛸 Ficção": 878,
    "🕵️ Suspense": 53, "🧸 Animação": 16, "💖 Romance": 10749, "📚 Drama": 18,
}
EPOCAS_MENU = {
    "🎸 Anos 80": (1980, 1989), "💾 Anos 90": (1990, 1999),
    "💿 Anos 2000": (2000, 2010), "🆕 Recentes": (2020, 2026),
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")


# ================= HEALTHCHECK HTTP (necessário para o Zeabur não marcar como crashed) =================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK - Bot rodando")

    def log_message(self, *args, **kwargs):
        pass  # silencia logs de acesso


def start_healthcheck_server():
    port = int(os.environ.get("PORT", "8000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logging.info(f"🌐 Healthcheck HTTP ativo na porta {port}")
    server.serve_forever()


# ================= BANCO DE DADOS =================
def get_db_connection():
    res = urlparse(DATABASE_URL)
    return psycopg2.connect(
        dbname=res.path[1:], user=res.username, password=res.password,
        host=res.hostname, port=res.port, connect_timeout=10,
    )


def setup_database():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS subscribed_chats (chat_id BIGINT PRIMARY KEY);")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sent_items (
                item_id BIGINT NOT NULL,
                item_type TEXT NOT NULL,
                sent_at TIMESTAMP NOT NULL,
                PRIMARY KEY (item_id, item_type)
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
        logging.info("✅ Banco de dados pronto.")
    except Exception as e:
        logging.error(f"Erro ao configurar banco: {e}")


def add_chat_to_db(chat_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO subscribed_chats (chat_id) VALUES (%s) ON CONFLICT (chat_id) DO NOTHING;", (chat_id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logging.error(f"Erro ao salvar chat: {e}")


def get_recently_sent_ids(item_type):
    """Retorna o conjunto de IDs já enviados recentemente, para evitar repetição."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        limite = datetime.utcnow() - timedelta(days=DIAS_SEM_REPETIR)
        cur.execute("SELECT item_id FROM sent_items WHERE item_type = %s AND sent_at > %s;", (item_type, limite))
        ids = {row[0] for row in cur.fetchall()}
        cur.close()
        conn.close()
        return ids
    except Exception as e:
        logging.error(f"Erro ao buscar itens enviados: {e}")
        return set()


def mark_item_sent(item_id, item_type):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO sent_items (item_id, item_type, sent_at) VALUES (%s, %s, %s)
               ON CONFLICT (item_id, item_type) DO UPDATE SET sent_at = EXCLUDED.sent_at;""",
            (item_id, item_type, datetime.utcnow()),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logging.error(f"Erro ao marcar item enviado: {e}")


def filtrar_nao_repetidos(itens, item_type):
    """Remove itens já enviados recentemente. Se sobrar pouco, mantém alguns originais."""
    ja_enviados = get_recently_sent_ids(item_type)
    novos = [i for i in itens if i.get("id") not in ja_enviados]
    return novos if novos else itens


# ================= TMDB & BUSCA INTELIGENTE DE TRAILER =================
def make_tmdb_request(endpoint, params=None, tentativas=2):
    base = "https://api.themoviedb.org/3"
    p = {"api_key": TMDB_API_KEY, "language": "pt-BR", **(params or {})}
    for tentativa in range(tentativas):
        try:
            r = requests.get(f"{base}/{endpoint}", params=p, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logging.warning(f"Tentativa {tentativa + 1} falhou para {endpoint}: {e}")
            time.sleep(1)
    return None


def buscar_trailer_boost(item_id, titulo, is_tv=False):
    v = make_tmdb_request(f"{'tv' if is_tv else 'movie'}/{item_id}/videos")
    if v and v.get("results"):
        video_list = v.get("results")
        trailer_obj = next((vid for vid in video_list if vid["type"] == "Trailer" and vid["site"] == "YouTube"), None)
        if trailer_obj:
            return f"https://youtube.com/watch?v={trailer_obj['key']}"
        yt_vid = next((vid for vid in video_list if vid["site"] == "YouTube"), None)
        if yt_vid:
            return f"https://youtube.com/watch?v={yt_vid['key']}"

    busca_query = quote(f"{titulo} Trailer Oficial Português")
    return f"https://www.youtube.com/results?search_query={busca_query}"


# ================= FUNÇÃO DE ENVIO NO TÓPICO 4342 =================
async def enviar_no_topico(context, text=None, photo=None, caption=None, reply_markup=None, parse_mode="HTML"):
    """Envia mensagem SEMPRE no tópico configurado do grupo."""
    kwargs = {"parse_mode": parse_mode}
    if TOPIC_ID:
        kwargs["message_thread_id"] = TOPIC_ID
    if reply_markup:
        kwargs["reply_markup"] = reply_markup

    try:
        if photo:
            return await context.bot.send_photo(GRUPO_ID, photo, caption=caption, **kwargs)
        elif text:
            return await context.bot.send_message(GRUPO_ID, text, **kwargs)
    except Exception as e:
        logging.error(f"Erro ao enviar no tópico {TOPIC_ID}: {e}")
        # fallback: tenta sem o tópico, caso o tópico tenha sido apagado/alterado
        try:
            kwargs.pop("message_thread_id", None)
            if photo:
                return await context.bot.send_photo(GRUPO_ID, photo, caption=caption, **kwargs)
            elif text:
                return await context.bot.send_message(GRUPO_ID, text, **kwargs)
        except Exception as e2:
            logging.error(f"Erro no fallback de envio: {e2}")


async def send_item_info(context, item, is_tv=False, item_type="movie"):
    if not item:
        return
    iid = item.get("id")
    title = item.get("name") if is_tv else item.get("title")
    rating = item.get("vote_average", 0)
    stars = "⭐" * max(1, round(rating / 2)) if rating else "—"

    data_lanc = item.get("first_air_date") if is_tv else item.get("release_date")
    ano = data_lanc[:4] if data_lanc else "?"

    sinopse = item.get("overview") or "Sinopse não disponível."
    if len(sinopse) > 280:
        sinopse = sinopse[:280].rsplit(" ", 1)[0] + "..."

    caption = (
        f"{'📺' if is_tv else '🎬'} <b>{html.escape(title)}</b> ({ano})\n\n"
        f"{stars} ({rating:.1f}/10)\n"
        f"📖 {html.escape(sinopse)}"
    )

    trailer_url = buscar_trailer_boost(iid, title, is_tv)

    # Link direto para o filme/série no site
    titulo_url = quote(title)
    link_filme = f"{SITE_URL}/search?q={titulo_url}"

    keyboard = [
        [InlineKeyboardButton("▶ ASSISTIR AGORA", url=link_filme)],
        [InlineKeyboardButton("💬 BAIXAR APP AQUI", url=APP_URL)],
    ]

    post = item.get("poster_path")
    markup = InlineKeyboardMarkup(keyboard)

    try:
        if post:
            await enviar_no_topico(context, photo=f"{TMDB_IMAGE_BASE_URL}{post}", caption=caption, reply_markup=markup)
        else:
            await enviar_no_topico(context, text=caption, reply_markup=markup)

        if trailer_url:
            await enviar_no_topico(context, text=f"🎥 <b>Confira o Trailer:</b>\n{trailer_url}")

        mark_item_sent(iid, item_type)
    except Exception as e:
        logging.error(f"Erro ao enviar item: {e}")


async def enviar_lista(context, itens, is_tv=False, item_type="movie", limite=3):
    itens = filtrar_nao_repetidos(itens, item_type)
    random.shuffle(itens)
    for item in itens[:limite]:
        await send_item_info(context, item, is_tv=is_tv, item_type=item_type)


# ================= HANDLERS DE TEXTO =================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if update.effective_chat.id != GRUPO_ID:
        return

    if text == "🎥 Em Cartaz":
        d = make_tmdb_request("movie/now_playing", {"region": "BR"})
        if d:
            await enviar_lista(context, d.get("results", []), item_type="now_playing")

    elif text == "🚀 Em Breve":
        d = make_tmdb_request("movie/upcoming", {"region": "BR"})
        if d:
            await enviar_lista(context, d.get("results", []), item_type="upcoming")

    elif text == "🌟 Populares":
        d = make_tmdb_request("movie/popular", {"region": "BR", "page": random.randint(1, 5)})
        if d:
            await enviar_lista(context, d.get("results", []), item_type="movie")

    elif text == "📺 Séries":
        d = make_tmdb_request("tv/popular", {"page": random.randint(1, 5)})
        if d:
            await enviar_lista(context, d.get("results", []), is_tv=True, item_type="tv")

    elif text == "🔥 Em Alta":
        d = make_tmdb_request("trending/all/week")
        if d:
            filmes = [i for i in d.get("results", []) if i.get("media_type") in ("movie", "tv")]
            for item in filmes[:4]:
                is_tv = item.get("media_type") == "tv"
                await send_item_info(context, item, is_tv=is_tv, item_type="tv" if is_tv else "movie")

    elif text == "🎭 Por Gênero":
        btns = [[InlineKeyboardButton(n, callback_data=f"gen_{i}")] for n, i in GENEROS_MENU.items()]
        await enviar_no_topico(context, text="✨ <b>Escolha um Gênero:</b>", reply_markup=InlineKeyboardMarkup(btns))

    elif text == "🎞️ Por Época":
        btns = [[InlineKeyboardButton(n, callback_data=f"era_{n}")] for n in EPOCAS_MENU.keys()]
        await enviar_no_topico(context, text="⏳ <b>Escolha uma Época:</b>", reply_markup=InlineKeyboardMarkup(btns))

    elif text == "🎲 Sugestão":
        d = make_tmdb_request("movie/top_rated", {"page": random.randint(1, 20)})
        if d and d.get("results"):
            await enviar_lista(context, d["results"], item_type="movie", limite=1)

    elif text == "🔍 Buscar":
        await enviar_no_topico(context, text="⌨️ Digite: <code>/filme Nome do Filme</code>\nou <code>/serie Nome da Série</code>")

    elif text == "❓ Ajuda":
        await enviar_ajuda(context)


# ================= CALLBACKS =================
async def callback_handler(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("gen_"):
        gid = data.split("_")[1]
        d = make_tmdb_request("discover/movie", {"with_genres": gid, "sort_by": "popularity.desc", "page": random.randint(1, 5)})
        if d and d.get("results"):
            await enviar_lista(context, d["results"], item_type="movie")

    elif data.startswith("era_"):
        era_nome = data.split("_", 1)[1]
        inicio, fim = EPOCAS_MENU[era_nome]
        ano_sorteado = random.randint(inicio, fim)
        d = make_tmdb_request("discover/movie", {"primary_release_year": ano_sorteado, "sort_by": "popularity.desc", "page": 1})
        if d and d.get("results"):
            await enviar_no_topico(context, text=f"🎞️ <b>Buscando os melhores de {ano_sorteado}...</b>")
            await enviar_lista(context, d["results"][:10], item_type="movie")


# ================= COMANDOS =================
async def avisogeral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("⚠️ Use: /avisogeral sua mensagem aqui")
        return
    await enviar_no_topico(context, text=msg)
    await update.message.reply_text("📢 Aviso enviado no tópico!")


async def filme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Use: /filme Nome do Filme")
        return
    query = " ".join(context.args)
    d = make_tmdb_request("search/movie", {"query": query})
    resultados = d.get("results", []) if d else []
    if not resultados:
        await enviar_no_topico(context, text=f"😕 Nenhum filme encontrado para: <b>{html.escape(query)}</b>")
        return
    await send_item_info(context, resultados[0], item_type="movie")


async def serie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Use: /serie Nome da Série")
        return
    query = " ".join(context.args)
    d = make_tmdb_request("search/tv", {"query": query})
    resultados = d.get("results", []) if d else []
    if not resultados:
        await enviar_no_topico(context, text=f"😕 Nenhuma série encontrada para: <b>{html.escape(query)}</b>")
        return
    await send_item_info(context, resultados[0], is_tv=True, item_type="tv")


async def enviar_ajuda(context):
    texto = (
        "❓ <b>Como usar o bot:</b>\n\n"
        "🎥 <b>Em Cartaz</b> — filmes nos cinemas agora\n"
        "🚀 <b>Em Breve</b> — lançamentos futuros\n"
        "🌟 <b>Populares</b> — filmes mais assistidos\n"
        "📺 <b>Séries</b> — séries populares\n"
        "🔥 <b>Em Alta</b> — destaques da semana\n"
        "🎭 <b>Por Gênero</b> — escolha o estilo\n"
        "🎞️ <b>Por Época</b> — filmes por década\n"
        "🎲 <b>Sugestão</b> — recomendação aleatória\n\n"
        "🔍 <b>Comandos:</b>\n"
        "<code>/filme Nome</code> — busca um filme específico\n"
        "<code>/serie Nome</code> — busca uma série específica\n"
        "<code>/start</code> — mostra o menu principal"
    )
    await enviar_no_topico(context, text=texto)


async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await enviar_ajuda(context)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_chat_to_db(update.effective_chat.id)
    user = update.effective_user

    kb = [
        ["🎥 Em Cartaz", "🚀 Em Breve"],
        ["🌟 Populares", "📺 Séries"],
        ["🔥 Em Alta", "🎲 Sugestão"],
        ["🎭 Por Gênero", "🎞️ Por Época"],
        ["🔍 Buscar", "❓ Ajuda"],
    ]

    promo_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 ACESSAR SITE OFICIAL", url=SITE_URL)],
        [InlineKeyboardButton("💬 BAIXAR APP AQUI", url=APP_URL)],
    ])

    await enviar_no_topico(
        context,
        text=f"🎬 <b>CineSky v5.0 - Cine Mega</b>\n\nOlá {html.escape(user.first_name)}! Tudo pronto para sua sessão de cinema hoje?",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
    )
    await enviar_no_topico(context, text="Acesse nosso site oficial para assistir agora:", reply_markup=promo_kb)


# ================= MAIN =================
def main():
    setup_database()

    # Servidor HTTP em segundo plano para o Zeabur reconhecer o app como "vivo"
    threading.Thread(target=start_healthcheck_server, daemon=True).start()

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ajuda", ajuda))
    application.add_handler(CommandHandler("avisogeral", avisogeral))
    application.add_handler(CommandHandler("filme", filme))
    application.add_handler(CommandHandler("serie", serie))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(callback_handler))

    logging.info(f"✅ Bot Online - Site: {SITE_URL} | Tópico: {TOPIC_ID}")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            logging.error(f"💥 Erro fatal, reiniciando em 10s: {e}")
            time.sleep(10)
