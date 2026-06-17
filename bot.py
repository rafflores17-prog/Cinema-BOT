# ================= BOT DE CINEMA v6.0 — StreamFlix Edition =================
import os, html, time, random, logging, threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, quote
import requests, psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ── Variáveis de ambiente (configure no Zeabur/Koyeb) ──────────────────────
TOKEN       = os.environ.get("BOT_TOKEN",    "8158367501:AAEpU5YkliLbY9xddHohmbW6wTffM1ye49U")
TMDB_KEY    = os.environ.get("TMDB_API_KEY", "c90fb79a2f7d756a49bee848bce5f413")
DATABASE_URL= os.environ.get("DATABASE_URL", "postgresql://neondb_owner:npg_uc8fRtixQZ6U@ep-orange-band-anlv6zu6-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require")
SITE_URL    = os.environ.get("SITE_URL",     "https://streamflix-red.zeabur.app")
APP_URL     = os.environ.get("APP_URL",      "http://bgdv.online/ed7g1w")
GRUPO_ID    = int(os.environ.get("GRUPO_ID", "-1003177664821"))
TOPIC_ID    = int(os.environ.get("TOPIC_ID", "4342"))
DIAS_SEM_REPETIR = 21

IMG_BASE  = "https://image.tmdb.org/t/p/w500"
TMDB_BASE = "https://api.themoviedb.org/3"

GENEROS = {"🔥 Ação":28,"🤡 Comédia":35,"👻 Terror":27,"🛸 Ficção":878,
           "🕵️ Suspense":53,"🧸 Animação":16,"💖 Romance":10749,"📚 Drama":18}
EPOCAS  = {"🎸 Anos 80":(1980,1989),"💾 Anos 90":(1990,1999),
           "💿 Anos 2000":(2000,2010),"🆕 Recentes":(2020,2026)}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ── Healthcheck ────────────────────────────────────────────────────────────
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type","text/plain"); self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self,*a,**k): pass

def start_health():
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT","8000"))), Health).serve_forever()

# ── Banco ──────────────────────────────────────────────────────────────────
def db():
    r=urlparse(DATABASE_URL)
    return psycopg2.connect(dbname=r.path[1:],user=r.username,password=r.password,
                            host=r.hostname,port=r.port,connect_timeout=10)

def setup_db():
    try:
        c=db(); cur=c.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS subscribed_chats (chat_id BIGINT PRIMARY KEY);")
        cur.execute("""CREATE TABLE IF NOT EXISTS sent_items (
            item_id BIGINT NOT NULL, item_type TEXT NOT NULL, sent_at TIMESTAMP NOT NULL,
            PRIMARY KEY (item_id, item_type));""")
        c.commit(); cur.close(); c.close()
        logging.info("✅ Banco pronto")
    except Exception as e: logging.error(f"Banco: {e}")

def ja_enviados(tipo):
    try:
        c=db(); cur=c.cursor()
        cur.execute("SELECT item_id FROM sent_items WHERE item_type=%s AND sent_at>%s",
                    (tipo, datetime.utcnow()-timedelta(days=DIAS_SEM_REPETIR)))
        ids={r[0] for r in cur.fetchall()}; cur.close(); c.close(); return ids
    except: return set()

def marcar(item_id, tipo):
    try:
        c=db(); cur=c.cursor()
        cur.execute("""INSERT INTO sent_items VALUES(%s,%s,%s)
            ON CONFLICT(item_id,item_type) DO UPDATE SET sent_at=EXCLUDED.sent_at""",
            (item_id,tipo,datetime.utcnow()))
        c.commit(); cur.close(); c.close()
    except Exception as e: logging.error(e)

def filtrar(itens, tipo):
    env=ja_enviados(tipo); novos=[i for i in itens if i.get("id") not in env]
    return novos if novos else itens

# ── TMDB ───────────────────────────────────────────────────────────────────
def tmdb(endpoint, params=None):
    p={"api_key":TMDB_KEY,"language":"pt-BR",**(params or {})}
    for _ in range(2):
        try:
            r=requests.get(f"{TMDB_BASE}/{endpoint}",params=p,timeout=15); r.raise_for_status()
            return r.json()
        except Exception as e: logging.warning(e); time.sleep(1)
    return None

def trailer(item_id, titulo, tv=False):
    v=tmdb(f"{'tv' if tv else 'movie'}/{item_id}/videos")
    if v and v.get("results"):
        res=v["results"]
        t=next((x for x in res if x["type"]=="Trailer" and x["site"]=="YouTube"),None)
        if t: return f"https://youtu.be/{t['key']}"
        yt=next((x for x in res if x["site"]=="YouTube"),None)
        if yt: return f"https://youtu.be/{yt['key']}"
    return f"https://www.youtube.com/results?search_query={quote(titulo+' Trailer')}"

# ── Link direto StreamFlix (deep link com ID do TMDB) ─────────────────────
def link_streamflix(item_id, titulo, is_tv=False):
    """Gera link que abre direto o detalhe do filme/série no StreamFlix."""
    tipo = "tv" if is_tv else "movie"
    # Tenta link de deep link com ID. Se o app suportar #detail-{id}
    return f"{SITE_URL}/#detail-{item_id}-{tipo}"

def link_busca(titulo):
    return f"{SITE_URL}/?q={quote(titulo)}"

# ── Envio ──────────────────────────────────────────────────────────────────
async def enviar(context, text=None, photo=None, caption=None, markup=None, parse_mode="HTML"):
    kw={"parse_mode":parse_mode}
    if TOPIC_ID: kw["message_thread_id"]=TOPIC_ID
    if markup:   kw["reply_markup"]=markup
    try:
        if photo:  return await context.bot.send_photo(GRUPO_ID,photo,caption=caption,**kw)
        elif text: return await context.bot.send_message(GRUPO_ID,text,**kw)
    except Exception as e:
        logging.error(f"Envio: {e}")
        kw.pop("message_thread_id",None)
        try:
            if photo:  return await context.bot.send_photo(GRUPO_ID,photo,caption=caption,**kw)
            elif text: return await context.bot.send_message(GRUPO_ID,text,**kw)
        except Exception as e2: logging.error(f"Fallback: {e2}")

async def send_item(context, item, is_tv=False, tipo="movie"):
    if not item: return
    iid   = item.get("id")
    title = item.get("name") if is_tv else item.get("title")
    rat   = item.get("vote_average",0)
    stars = "⭐"*max(1,round(rat/2)) if rat else "—"
    ano   = (item.get("first_air_date") if is_tv else item.get("release_date",""))[:4] or "?"
    sinopse = item.get("overview") or "Sinopse não disponível."
    if len(sinopse)>280: sinopse=sinopse[:280].rsplit(" ",1)[0]+"…"

    caption=(f"{'📺' if is_tv else '🎬'} <b>{html.escape(title)}</b> ({ano})\n\n"
             f"{stars} ({rat:.1f}/10)\n📖 {html.escape(sinopse)}")

    url_direto  = link_streamflix(iid, title, is_tv)
    url_trailer = trailer(iid, title, is_tv)

    keyboard=[[InlineKeyboardButton("▶️ ASSISTIR NO STREAMFLIX", url=url_direto)],
              [InlineKeyboardButton("🎥 Ver Trailer", url=url_trailer),
               InlineKeyboardButton("📱 Baixar App", url=APP_URL)]]

    post=item.get("poster_path")
    try:
        if post: await enviar(context,photo=f"{IMG_BASE}{post}",caption=caption,markup=InlineKeyboardMarkup(keyboard))
        else:    await enviar(context,text=caption,markup=InlineKeyboardMarkup(keyboard))
        marcar(iid,tipo)
    except Exception as e: logging.error(e)

async def enviar_lista(context, itens, is_tv=False, tipo="movie", limite=3):
    itens=filtrar(itens,tipo); random.shuffle(itens)
    for item in itens[:limite]: await send_item(context,item,is_tv=is_tv,tipo=tipo)

# ── Handlers ───────────────────────────────────────────────────────────────
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text=update.message.text
    if update.effective_chat.id!=GRUPO_ID: return

    if text=="🎥 Em Cartaz":
        d=tmdb("movie/now_playing",{"region":"BR"})
        if d: await enviar_lista(context,d.get("results",[]),tipo="now_playing")
    elif text=="🚀 Em Breve":
        d=tmdb("movie/upcoming",{"region":"BR"})
        if d: await enviar_lista(context,d.get("results",[]),tipo="upcoming")
    elif text=="🌟 Populares":
        d=tmdb("movie/popular",{"region":"BR","page":random.randint(1,5)})
        if d: await enviar_lista(context,d.get("results",[]))
    elif text=="📺 Séries":
        d=tmdb("tv/popular",{"page":random.randint(1,5)})
        if d: await enviar_lista(context,d.get("results",[]),is_tv=True,tipo="tv")
    elif text=="🔥 Em Alta":
        d=tmdb("trending/all/week")
        if d:
            for item in d.get("results",[])[:4]:
                is_tv=item.get("media_type")=="tv"
                await send_item(context,item,is_tv=is_tv,tipo="tv" if is_tv else "movie")
    elif text=="🎭 Por Gênero":
        btns=[[InlineKeyboardButton(n,callback_data=f"gen_{i}")] for n,i in GENEROS.items()]
        await enviar(context,text="✨ <b>Escolha um Gênero:</b>",markup=InlineKeyboardMarkup(btns))
    elif text=="🎞️ Por Época":
        btns=[[InlineKeyboardButton(n,callback_data=f"era_{n}")] for n in EPOCAS]
        await enviar(context,text="⏳ <b>Escolha uma Época:</b>",markup=InlineKeyboardMarkup(btns))
    elif text=="🎲 Sugestão":
        d=tmdb("movie/top_rated",{"page":random.randint(1,20)})
        if d and d.get("results"): await enviar_lista(context,d["results"],limite=1)
    elif text=="🔍 Buscar":
        await enviar(context,text="⌨️ <code>/filme Nome do Filme</code>\nou <code>/serie Nome da Série</code>")
    elif text=="❓ Ajuda":
        await cmd_ajuda_fn(context)

async def callback_handler(update, context):
    q=update.callback_query; await q.answer(); data=q.data
    if data.startswith("gen_"):
        gid=data.split("_")[1]
        d=tmdb("discover/movie",{"with_genres":gid,"sort_by":"popularity.desc","page":random.randint(1,5)})
        if d and d.get("results"): await enviar_lista(context,d["results"])
    elif data.startswith("era_"):
        era=data.split("_",1)[1]; inicio,fim=EPOCAS[era]
        ano=random.randint(inicio,fim)
        d=tmdb("discover/movie",{"primary_release_year":ano,"sort_by":"popularity.desc","page":1})
        if d and d.get("results"):
            await enviar(context,text=f"🎞️ <b>Melhores de {ano}...</b>")
            await enviar_lista(context,d["results"][:10])

# ── Comandos ───────────────────────────────────────────────────────────────
async def cmd_filme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("⚠️ Use: /filme Nome do Filme"); return
    q=" ".join(context.args); d=tmdb("search/movie",{"query":q})
    res=d.get("results",[]) if d else []
    if not res: await enviar(context,text=f"😕 Filme não encontrado: <b>{html.escape(q)}</b>"); return
    await send_item(context,res[0],tipo="movie")

async def cmd_serie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("⚠️ Use: /serie Nome da Série"); return
    q=" ".join(context.args); d=tmdb("search/tv",{"query":q})
    res=d.get("results",[]) if d else []
    if not res: await enviar(context,text=f"😕 Série não encontrada: <b>{html.escape(q)}</b>"); return
    await send_item(context,res[0],is_tv=True,tipo="tv")

async def cmd_avisogeral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg=" ".join(context.args)
    if not msg: await update.message.reply_text("⚠️ /avisogeral mensagem"); return
    await enviar(context,text=msg)
    await update.message.reply_text("📢 Aviso enviado!")

async def cmd_ajuda_fn(context):
    texto=("❓ <b>Comandos:</b>\n\n"
           "🎥 <b>Em Cartaz</b> — cinemas agora\n🚀 <b>Em Breve</b> — próximos lançamentos\n"
           "🌟 <b>Populares</b> — mais vistos\n📺 <b>Séries</b> — séries em alta\n"
           "🔥 <b>Em Alta</b> — trending da semana\n🎭 <b>Por Gênero</b> — filtre por estilo\n"
           "🎞️ <b>Por Época</b> — por década\n🎲 <b>Sugestão</b> — surpresa aleatória\n\n"
           "<code>/filme Nome</code> — busca filme\n<code>/serie Nome</code> — busca série")
    await enviar(context,text=texto)

async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_ajuda_fn(context)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        c=db(); cur=c.cursor()
        cur.execute("INSERT INTO subscribed_chats VALUES(%s) ON CONFLICT DO NOTHING",(update.effective_chat.id,))
        c.commit(); cur.close(); c.close()
    except: pass
    user=update.effective_user
    kb=[["🎥 Em Cartaz","🚀 Em Breve"],["🌟 Populares","📺 Séries"],
        ["🔥 Em Alta","🎲 Sugestão"],["🎭 Por Gênero","🎞️ Por Época"],["🔍 Buscar","❓ Ajuda"]]
    promo=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 ACESSAR STREAMFLIX",url=SITE_URL)],
                                [InlineKeyboardButton("📱 BAIXAR APP",url=APP_URL)]])
    await enviar(context,
        text=f"🎬 <b>StreamFlix Bot</b>\n\nOlá {html.escape(user.first_name)}! Pronto para assistir?",
        markup=ReplyKeyboardMarkup(kb,resize_keyboard=True))
    await enviar(context,text="Acesse o StreamFlix:",markup=promo)

# ── Main ───────────────────────────────────────────────────────────────────
def main():
    setup_db()
    threading.Thread(target=start_health,daemon=True).start()
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("ajuda",   cmd_ajuda))
    app.add_handler(CommandHandler("avisogeral", cmd_avisogeral))
    app.add_handler(CommandHandler("filme",   cmd_filme))
    app.add_handler(CommandHandler("serie",   cmd_serie))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(callback_handler))
    logging.info(f"✅ Bot Online — {SITE_URL}")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    while True:
        try: main()
        except Exception as e: logging.error(f"💥 Reiniciando: {e}"); time.sleep(10)
