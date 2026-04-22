# ================= BOT DE CINEMA v4.0 (REVISÃO COMPLETA) =================
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
# Dicionário de Gêneros para o Menu Inteligente
GENEROS_MENU = {"Ação": 28, "Comédia": 35, "Terror": 27, "Animação": 16, "Ficção": 878, "Suspense": 53}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

# ================= DB & AUX =================
def get_db_connection():
    res = urlparse(DATABASE_URL)
    return psycopg2.connect(dbname=res.path[1:], user=res.username, password=res.password, host=res.hostname, port=res.port)

def make_tmdb_request(endpoint, params={}):
    base = "https://api.themoviedb.org/3"
    p = {"api_key": TMDB_API_KEY, "language": "pt-BR", **params}
    try:
        r = requests.get(f"{base}/{endpoint}", params=p, timeout=10)
        return r.json()
    except: return None

# ================= ENVIO DE CONTEÚDO =================
async def send_item_info(context, chat_id, item, is_tv=False):
    if not item: return
    iid = item.get("id")
    title = item.get("name") if is_tv else item.get("title")
    caption = (f"{'📺' if is_tv else '🎬'} <b>{html.escape(title)}</b>\n\n"
               f"⭐ {item.get('vote_average', 0):.1f}/10\n"
               f"📖 {item.get('overview', 'Sem sinopse')[:300]}...")
    
    q_online = quote(f"assistir {title} dublado online")
    q_torrent = quote(f"baixar {title} torrent dublado 1080p")
    
    keyboard = [
        [InlineKeyboardButton("🎬 Ver Trailer", callback_data=f"tr_{'tv' if is_tv else 'mv'}_{iid}")],
        [InlineKeyboardButton("📺 Assistir Online", url=f"https://duckduckgo.com/?q={q_online}")],
        [InlineKeyboardButton("📥 Buscar Torrent", url=f"https://duckduckgo.com/?q={q_torrent}")]
    ]
    
    post = item.get("poster_path")
    markup = InlineKeyboardMarkup(keyboard)
    if post:
        await context.bot.send_photo(chat_id, f"{TMDB_IMAGE_BASE_URL}{post}", caption=caption, parse_mode='HTML', reply_markup=markup)
    else:
        await context.bot.send_message(chat_id, caption, parse_mode='HTML', reply_markup=markup)

# ================= HANDLERS =================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id
    
    if text == '🎬 Filmes em Cartaz':
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
        # Cria botões para os gêneros em vez de pedir ID
        btns = [[InlineKeyboardButton(n, callback_data=f"gen_{i}")] for n, i in GENEROS_MENU.items()]
        await update.message.reply_text("Escolha um gênero:", reply_markup=InlineKeyboardMarkup(btns))
        
    elif text == '🎲 Aleatório':
        d = make_tmdb_request("movie/top_rated", {"page": random.randint(1, 10)})
        if d.get('results'): await send_item_info(context, chat_id, random.choice(d['results']))

async def callback_handler(update, context):
    query = update.callback_query; await query.answer()
    data = query.data
    
    if data.startswith("tr_"):
        parts = data.split("_")
        path = f"{'tv' if parts[1]=='tv' else 'movie'}/{parts[2]}/videos"
        v = make_tmdb_request(path)
        link = next((f"https://youtube.com/watch?v={i['key']}" for i in v.get('results', []) if i['type'] == 'Trailer'), None)
        await query.message.reply_text(f"🎥 Trailer: {link}" if link else "❌ Não encontrado.")
        
    elif data.startswith("gen_"):
        gid = data.split("_")[1]
        d = make_tmdb_request("discover/movie", {"with_genres": gid})
        for m in d.get('results', [])[:3]: await send_item_info(context, chat_id=query.message.chat_id, item=m)

async def start(update, context):
    kb = [['🎬 Filmes em Cartaz', '🚀 Em Breve'], ['🌟 Populares', '📺 Séries'], ['🎭 Por Gênero', '🎲 Aleatório']]
    await update.message.reply_text("🎬 <b>CineSky V4.0</b>", parse_mode='HTML', reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.run_polling()

if __name__ == "__main__": main()
