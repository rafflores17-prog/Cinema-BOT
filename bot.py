# ================= BOT DE CINEMA v4.5 (INTEGRAÇÃO CINE MEGA) =================
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
SITE_URL = "https://www.cinemega.online" # Seu domínio oficial

# Dicionários de Configuração Visual
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

# ================= TMDB & BUSCA =================
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
    rating = item.get("vote_average", 0)
    stars = "⭐" * round(rating / 2)
    
    caption = (f"{'📺' if is_tv else '🎬'} <b>{html.escape(title)}</b>\n\n"
               f"{stars} ({rating:.1f}/10)\n"
               f"📖 {item.get('overview', 'Sinopse não disponível.')[:280]}...")
    
    # Lógica Cine Mega: Redireciona para a página do filme no seu site
    link_assistir = f"{SITE_URL}/filme/{iid}"
    q_torrent = quote(f"{title} download torrent dublado 1080p")
    
    keyboard = [
        [InlineKeyboardButton("🚀 ASSISTIR ONLINE (VIP)", url=link_assistir)],
        [InlineKeyboardButton("🎬 Trailer", callback_data=f"tr_{'tv' if is_tv else 'mv'}_{iid}"),
         InlineKeyboardButton("📥 Torrent", url=f"https://duckduckgo.com/?q={q_torrent}")]
    ]
    
    post = item.get("poster_path")
    markup = InlineKeyboardMarkup(keyboard)
    try:
        if post:
            await context.bot.send_photo(chat_id, f"{TMDB_IMAGE_BASE_URL}{post}", caption=caption, parse_mode='HTML', reply_markup=markup)
        else:
            await context.bot.send_message(chat_id, caption, parse_mode='HTML', reply_markup=markup)
    except: pass

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
    
    if data.startswith("tr_"):
        p = data.split("_")
        path = f"{'tv' if p[1]=='tv' else 'movie'}/{p[2]}/videos"
        v = make_tmdb_request(path)
        link = next((f"https://youtube.com/watch?v={i['key']}" for i in v.get('results', []) if i['type'] == 'Trailer'), None)
        await query.message.reply_text(f"🎥 Trailer: {link}" if link else "❌ Trailer não disponível.")
        
    elif data.startswith("gen_"):
        gid = data.split("_")[1]
        d = make_tmdb_request("discover/movie", {"with_genres": gid, "page": random.randint(1, 5)})
        if d.get('results'):
            filmes = d.get('results'); random.shuffle(filmes)
            for m in filmes[:3]: await send_item_info(context, chat_id, m)

    elif data.startswith("era_"):
        era_nome = data.split("_")[1]
        inicio, fim = EPOCAS_MENU[era_nome]
        ano_sorteado = random.randint(inicio, fim)
        d = make_tmdb_request("discover/movie", {"primary_release_year": ano_sorteado, "sort_by": "popularity.desc", "page": random.randint(1, 3)})
        if d.get('results'):
            filmes = d.get('results'); random.shuffle(filmes)
            await context.bot.send_message(chat_id, f"🎬 <b>Clássicos de {ano_sorteado}:</b>", parse_mode='HTML')
            for m in filmes[:3]: await send_item_info(context, chat_id, m)

# ================= COMANDO BROADCAST (AVISO GERAL) =================
@app.route # Apenas lembrete: este comando é para o dono do bot
async def avisogeral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != 123456789: # TROQUE PELO SEU ID DO TELEGRAM
        return
    msg = " ".join(context.args)
    if not msg: return
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("SELECT chat_id FROM subscribed_chats")
    chats = cur.fetchall()
    count = 0
    for chat in chats:
        try:
            await context.bot.send_message(chat[0], msg, parse_mode='HTML')
            count += 1
        except: continue
    await update.message.reply_text(f"📢 Aviso enviado para {count} usuários!")

# ================= START & MAIN =================
async def start(update, context):
    add_chat_to_db(update.effective_chat.id)
    kb = [['🎥 Em Cartaz', '🚀 Em Breve'], ['🌟 Populares', '📺 Séries'], ['🎭 Por Gênero', '🎞️ Por Época'], ['🎲 Sugestão', '🔍 Buscar']]
    
    # Propaganda do Site e App
    promo_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Acessar Site Oficial", url=SITE_URL)],
        [InlineKeyboardButton("📱 Baixar App (Android)", url="https://t.me/APKBUGADO")] # Canal onde está o APK
    ])
    
    await update.message.reply_text(
        f"🎬 <b>CineSky v4.5 - Integrado ao Cine Mega</b>\n\nAgora você pode assistir seus filmes favoritos diretamente no nosso site oficial ou via APK!",
        parse_mode='HTML', reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    await update.message.reply_text("Escolha uma opção ou use nossos links oficiais:", reply_markup=promo_kb)

def main():
    setup_database()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('filme', lambda u, c: send_item_info(c, u.effective_chat.id, make_tmdb_request("search/movie", {"query": " ".join(c.args)}).get('results', [None])[0]) if c.args else None))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(callback_handler))
    logging.info("CineSky v4.5 Online!")
    app.run_polling()

if __name__ == "__main__": main()
