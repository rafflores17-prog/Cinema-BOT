# ================= BOT DE CINEMA v4.7 (CINE MEGA EXCLUSIVE) =================
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
SITE_URL = "https://www.cinemega.online" 
APP_DOWNLOAD_URL = "http://bgdv.online/a4qjfr" # Seu link oficial

GENEROS_MENU = {"🔥 Ação": 28, "🤡 Comédia": 35, "👻 Terror": 27, "🛸 Ficção": 878, "🕵️ Suspense": 53, "🧸 Animação": 16}
EPOCAS_MENU = {"🎸 Anos 80": (1980, 1989), "💾 Anos 90": (1990, 1999), "💿 Anos 2000": (2000, 2010), "🆕 Recentes": (2020, 2026)}

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

# ================= TMDB & BUSCA INTELIGENTE DE TRAILER =================
def make_tmdb_request(endpoint, params={}):
    base = "https://api.themoviedb.org/3"
    p = {"api_key": TMDB_API_KEY, "language": "pt-BR", **params}
    try:
        r = requests.get(f"{base}/{endpoint}", params=p, timeout=10)
        return r.json()
    except: return None

def buscar_trailer_boost(item_id, titulo, is_tv=False):
    """Tenta o TMDB, se falhar, gera link de busca no YouTube para o Mini Play"""
    v = make_tmdb_request(f"{'tv' if is_tv else 'movie'}/{item_id}/videos")
    if v and v.get('results'):
        video_list = v.get('results')
        # Tenta achar o Trailer Oficial
        trailer_obj = next((vid for vid in video_list if vid['type'] == 'Trailer' and vid['site'] == 'YouTube'), None)
        if trailer_obj:
            return f"https://youtube.com/watch?v={trailer_obj['key']}"
        # Se não tiver tipo 'Trailer', pega qualquer vídeo do YT
        elif video_list:
            yt_vid = next((vid for vid in video_list if vid['site'] == 'YouTube'), None)
            if yt_vid: return f"https://youtube.com/watch?v={yt_vid['key']}"

    # BOOST: Se nada acima funcionar, cria link de busca (O Telegram tenta puxar o 1º resultado)
    busca_query = quote(f"{titulo} Trailer Oficial Português")
    return f"https://www.youtube.com/results?search_query={busca_query}"

async def send_item_info(context, chat_id, item, is_tv=False):
    if not item: return
    iid = item.get("id")
    title = item.get("name") if is_tv else item.get("title")
    rating = item.get("vote_average", 0)
    stars = "⭐" * round(rating / 2)
    
    caption = (f"{'📺' if is_tv else '🎬'} <b>{html.escape(title)}</b>\n\n"
               f"{stars} ({rating:.1f}/10)\n"
               f"📖 {item.get('overview', 'Sinopse não disponível.')[:280]}...")
    
    link_assistir = f"{SITE_URL}/filme/{iid}"
    
    # Busca turbinada de trailer para garantir o Mini Play
    trailer_url = buscar_trailer_boost(iid, title, is_tv)

    # BOTÕES PRINCIPAIS
    keyboard = [
        [InlineKeyboardButton("🚀 ASSISTIR ONLINE (Cine Mega)", url=link_assistir)],
        [InlineKeyboardButton("📲 BAIXAR APP OFICIAL (Android)", url=APP_DOWNLOAD_URL)]
    ]
    
    post = item.get("poster_path")
    markup = InlineKeyboardMarkup(keyboard)
    
    try:
        # 1. Envia a Foto/Sinopse com botões
        if post:
            await context.bot.send_photo(chat_id, f"{TMDB_IMAGE_BASE_URL}{post}", caption=caption, parse_mode='HTML', reply_markup=markup)
        else:
            await context.bot.send_message(chat_id, caption, parse_mode='HTML', reply_markup=markup)
        
        # 2. Envia o link do Trailer logo abaixo (Gera o player automático no Telegram)
        if trailer_url:
            await context.bot.send_message(chat_id, f"🎥 <b>Confira o Trailer:</b>\n{trailer_url}", parse_mode='HTML')
            
    except Exception as e:
        logging.error(f"Erro ao enviar: {e}")

# ================= HANDLERS DE TEXTO =================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id
    
    if text == '🎥 Em Cartaz':
        d = make_tmdb_request("movie/now_playing", {"region": "BR"})
        for m in d.get('results', [])[:3]: await send_item_info(context, chat_id, m)
    elif text == '🚀 Em Breve':
        d = make_tmdb_request("movie/upcoming", {"region": "BR"})
        for m in d.get('results', [])[:3]: await send_item_info(context, chat_id, m)
    elif text == '🌟 Populares':
        d = make_tmdb_request("movie/popular", {"region": "BR"})
        for m in d.get('results', [])[:3]: await send_item_info(context, chat_id, m)
    elif text == '📺 Séries':
        d = make_tmdb_request("tv/popular")
        for s in d.get('results', [])[:3]: await send_item_info(context, chat_id, s, is_tv=True)
    elif text == '🎭 Por Gênero':
        btns = [[InlineKeyboardButton(n, callback_data=f"gen_{i}")] for n, i in GENEROS_MENU.items()]
        await update.message.reply_text("✨ <b>Escolha um Gênero:</b>", parse_mode='HTML', reply_markup=InlineKeyboardMarkup(btns))
    elif text == '🎞️ Por Época':
        btns = [[InlineKeyboardButton(n, callback_data=f"era_{n}")] for n in EPOCAS_MENU.keys()]
        await update.message.reply_text("⏳ <b>Escolha uma Época:</b>", parse_mode='HTML', reply_markup=InlineKeyboardMarkup(btns))
    elif text == '🎲 Sugestão':
        d = make_tmdb_request("movie/top_rated", {"page": random.randint(1, 20)})
        if d.get('results'): await send_item_info(context, chat_id, random.choice(d['results']))
    elif text == '🔍 Buscar':
        await update.message.reply_text("⌨️ Digite: <code>/filme Nome do Filme</code>", parse_mode='HTML')

# ================= CALLBACKS =================
async def callback_handler(update, context):
    query = update.callback_query; await query.answer()
    data = query.data; chat_id = query.message.chat_id
    
    if data.startswith("gen_"):
        gid = data.split("_")[1]
        d = make_tmdb_request("discover/movie", {"with_genres": gid, "page": random.randint(1, 5)})
        if d and d.get('results'):
            filmes = d.get('results'); random.shuffle(filmes)
            for m in filmes[:3]: await send_item_info(context, chat_id, m)

    elif data.startswith("era_"):
        era_nome = data.split("_")[1]
        inicio, fim = EPOCAS_MENU[era_nome]
        ano_sorteado = random.randint(inicio, fim)
        d = make_tmdb_request("discover/movie", {"primary_release_year": ano_sorteado, "sort_by": "popularity.desc", "page": 1})
        if d and d.get('results'):
            await context.bot.send_message(chat_id, f"🎞️ <b>Buscando os melhores de {ano_sorteado}...</b>", parse_mode='HTML')
            filmes = d.get('results')[:10]; random.shuffle(filmes)
            for m in filmes[:3]: await send_item_info(context, chat_id, m)

# ================= COMANDOS E START =================
async def avisogeral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = " ".join(context.args)
    if not msg: return
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT chat_id FROM subscribed_chats")
    chats = cur.fetchall()
    for chat in chats:
        try: await context.bot.send_message(chat[0], msg, parse_mode='HTML')
        except: continue
    await update.message.reply_text("📢 Aviso enviado!")

async def start(update, context):
    add_chat_to_db(update.effective_chat.id)
    kb = [['🎥 Em Cartaz', '🚀 Em Breve'], ['🌟 Populares', '📺 Séries'], ['🎭 Por Gênero', '🎞️ Por Época'], ['🎲 Sugestão', '🔍 Buscar']]
    promo_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Acessar Site Oficial", url=SITE_URL)],
        [InlineKeyboardButton("📲 BAIXAR APP OFICIAL (Android)", url=APP_DOWNLOAD_URL)]
    ])
    await update.message.reply_text(
        f"🎬 <b>CineSky v4.7 - Cine Mega</b>\n\nOlá Mestre! Tudo pronto para sua sessão de cinema hoje?",
        parse_mode='HTML', reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    await update.message.reply_text("Use o menu abaixo ou baixe nosso App para assistir agora:", reply_markup=promo_kb)

def main():
    setup_database()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('avisogeral', avisogeral))
    application.add_handler(CommandHandler('filme', lambda u, c: send_item_info(c, u.effective_chat.id, make_tmdb_request("search/movie", {"query": " ".join(c.args)}).get('results', [None])[0]) if c.args else None))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(callback_handler))
    logging.info("CineSky v4.7 Online com Boost de Trailer!")
    application.run_polling()

if __name__ == "__main__": main()
