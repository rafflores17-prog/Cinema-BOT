# ================= BOT DE CINEMA v7.0 — StreamFlix Edition =================
# Melhorias v7:
#   ✅ Deep link corrigido: SITE_URL/#/title/{id}/{type}  (abre direto no filme)
#   ✅ Mais info no card: elenco, diretor, gêneros, duração, nota detalhada
#   ✅ Botão trailer com link do YouTube embutido (t.me/iv para preview inline)
#   ✅ Posts de séries com info de temporadas/episódios
#   ✅ /top10 — ranking semanal automático
#   ✅ /ator busca filmes por nome de ator
#   ✅ Postagem automática agendada diária (8h e 20h)
# ============================================================================

import os, html, time, random, logging, threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, quote
import requests, psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          filters, ContextTypes, CallbackQueryHandler, JobQueue)

# ── Variáveis de ambiente ──────────────────────────────────────────────────
TOKEN        = os.environ.get("BOT_TOKEN",    "SEU_TOKEN_AQUI")
TMDB_KEY     = os.environ.get("TMDB_API_KEY", "SUA_CHAVE_TMDB_AQUI")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
SITE_URL     = os.environ.get("SITE_URL",     "https://streamflix-red.zeabur.app")
APP_URL      = os.environ.get("APP_URL",      "https://streamflix-red.zeabur.app")
GRUPO_ID     = int(os.environ.get("GRUPO_ID", "0"))
TOPIC_ID     = int(os.environ.get("TOPIC_ID", "0"))
DIAS_SEM_REPETIR = 21

IMG_BASE  = "https://image.tmdb.org/t/p/w500"
TMDB_BASE = "https://api.themoviedb.org/3"

GENEROS = {
    "🔥 Ação":28, "🤡 Comédia":35, "👻 Terror":27, "🛸 Ficção Científica":878,
    "🕵️ Suspense":53, "🧸 Animação":16, "💖 Romance":10749, "📚 Drama":18,
    "🧩 Mistério":9648, "🎵 Musical":10402
}
EPOCAS = {
    "🎸 Anos 80":(1980,1989), "💾 Anos 90":(1990,1999),
    "💿 Anos 2000":(2000,2010), "🆕 Recentes":(2020,2026)
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ── Healthcheck ────────────────────────────────────────────────────────────
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type","text/plain")
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *a, **k): pass

def start_health():
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT","8000"))), Health).serve_forever()

# ── Banco ──────────────────────────────────────────────────────────────────
def db():
    r = urlparse(DATABASE_URL)
    return psycopg2.connect(
        dbname=r.path[1:], user=r.username, password=r.password,
        host=r.hostname, port=r.port, connect_timeout=10
    )

def setup_db():
    try:
        c = db(); cur = c.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS subscribed_chats (chat_id BIGINT PRIMARY KEY);")
        cur.execute("""CREATE TABLE IF NOT EXISTS sent_items (
            item_id BIGINT NOT NULL, item_type TEXT NOT NULL, sent_at TIMESTAMP NOT NULL,
            PRIMARY KEY (item_id, item_type));""")
        c.commit(); cur.close(); c.close()
        logging.info("✅ Banco pronto")
    except Exception as e:
        logging.error(f"Banco: {e}")

def ja_enviados(tipo):
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT item_id FROM sent_items WHERE item_type=%s AND sent_at>%s",
                    (tipo, datetime.utcnow()-timedelta(days=DIAS_SEM_REPETIR)))
        ids = {r[0] for r in cur.fetchall()}
        cur.close(); c.close()
        return ids
    except:
        return set()

def marcar(item_id, tipo):
    try:
        c = db(); cur = c.cursor()
        cur.execute("""INSERT INTO sent_items VALUES(%s,%s,%s)
            ON CONFLICT(item_id,item_type) DO UPDATE SET sent_at=EXCLUDED.sent_at""",
            (item_id, tipo, datetime.utcnow()))
        c.commit(); cur.close(); c.close()
    except Exception as e:
        logging.error(e)

def filtrar(itens, tipo):
    env = ja_enviados(tipo)
    novos = [i for i in itens if i.get("id") not in env]
    return novos if novos else itens

# ── TMDB ───────────────────────────────────────────────────────────────────
def tmdb(endpoint, params=None):
    p = {"api_key": TMDB_KEY, "language": "pt-BR", **(params or {})}
    for _ in range(2):
        try:
            r = requests.get(f"{TMDB_BASE}/{endpoint}", params=p, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logging.warning(e); time.sleep(1)
    return None

def tmdb_details(item_id, is_tv=False):
    """Busca detalhes completos: elenco, diretor, gêneros, runtime, etc."""
    tipo = "tv" if is_tv else "movie"
    extra = "credits,videos,external_ids"
    d = tmdb(f"{tipo}/{item_id}", {"append_to_response": extra})
    return d

def get_trailer_url(item_id, titulo, is_tv=False):
    """Retorna URL do YouTube do trailer."""
    v = tmdb(f"{'tv' if is_tv else 'movie'}/{item_id}/videos")
    if v and v.get("results"):
        res = v["results"]
        t = next((x for x in res if x["type"]=="Trailer" and x["site"]=="YouTube"), None)
        if t: return f"https://youtu.be/{t['key']}"
        yt = next((x for x in res if x["site"]=="YouTube"), None)
        if yt: return f"https://youtu.be/{yt['key']}"
    return f"https://www.youtube.com/results?search_query={quote(titulo+' Trailer Oficial')}"

def link_streamflix(item_id, is_tv=False):
    """
    ✅ Deep link correto para o app StreamFlix.
    Formato: SITE_URL/#/title/{id}/{type}
    O router do app detecta via hashchange e chama openDetailPage(id, type).
    """
    tipo = "tv" if is_tv else "movie"
    return f"{SITE_URL}/#/title/{item_id}/{tipo}"

def formatar_estrelas(rating):
    """Converte nota 0-10 em estrelas."""
    if not rating: return "—"
    cheias = round(rating / 2)
    return "⭐" * cheias + "☆" * (5 - cheias)

def formatar_runtime(minutos):
    """Formata duração em horas e minutos."""
    if not minutos: return ""
    h, m = divmod(minutos, 60)
    if h and m: return f"{h}h{m:02d}min"
    if h: return f"{h}h"
    return f"{m}min"

def build_caption(details, is_tv=False):
    """
    Monta caption completo com: título, ano, nota, gêneros, duração/temporadas,
    sinopse, elenco principal e diretor/criadores.
    """
    if not details:
        return "ℹ️ Informações indisponíveis."

    titulo   = details.get("name") if is_tv else details.get("title","?")
    orig_title = details.get("original_name" if is_tv else "original_title","")
    ano      = (details.get("first_air_date","") if is_tv else details.get("release_date",""))[:4] or "?"
    rating   = details.get("vote_average", 0)
    count    = details.get("vote_count", 0)
    sinopse  = details.get("overview") or "Sinopse não disponível."
    if len(sinopse) > 300: sinopse = sinopse[:300].rsplit(" ",1)[0] + "…"

    # Gêneros
    gen_list = [g["name"] for g in details.get("genres", [])]
    generos  = " • ".join(gen_list[:3]) if gen_list else ""

    # Duração / temporadas
    if is_tv:
        seasons  = details.get("number_of_seasons", 0)
        episodes = details.get("number_of_episodes", 0)
        duracao  = f"📺 {seasons} temp. • {episodes} eps." if seasons else ""
        status_raw = details.get("status","")
        status_map = {
            "Returning Series":"🟢 Em exibição",
            "Ended":"🔴 Encerrada",
            "Canceled":"⛔ Cancelada",
            "In Production":"🎬 Em produção",
        }
        status = status_map.get(status_raw, "")
    else:
        runtime  = details.get("runtime") or 0
        duracao  = f"⏱ {formatar_runtime(runtime)}" if runtime else ""
        status   = ""

    # Elenco (top 5)
    cast_list = []
    credits   = details.get("credits", {})
    cast      = credits.get("cast", [])
    for p in cast[:5]:
        cast_list.append(p.get("name",""))
    elenco = ", ".join(cast_list) if cast_list else ""

    # Diretor (filmes) ou criadores (séries)
    if is_tv:
        criadores = [c.get("name","") for c in details.get("created_by", [])]
        direcao_label = "✍️ Criado por"
        direcao_val   = ", ".join(criadores[:2]) if criadores else ""
    else:
        crew = credits.get("crew", [])
        diretores = [p["name"] for p in crew if p.get("job")=="Director"]
        direcao_label = "🎬 Direção"
        direcao_val   = ", ".join(diretores[:2]) if diretores else ""

    # Monta caption
    icone = "📺" if is_tv else "🎬"
    linhas = [f"{icone} <b>{html.escape(titulo)}</b> ({ano})"]

    if orig_title and orig_title != titulo:
        linhas.append(f"<i>{html.escape(orig_title)}</i>")

    linhas.append("")
    linhas.append(f"{formatar_estrelas(rating)} <b>{rating:.1f}/10</b> ({count:,} votos)")

    if generos:
        linhas.append(f"🎭 {html.escape(generos)}")
    if duracao:
        linhas.append(duracao)
    if status:
        linhas.append(status)

    linhas.append("")
    linhas.append(f"📖 {html.escape(sinopse)}")

    if elenco:
        linhas.append("")
        linhas.append(f"🌟 <b>Elenco:</b> {html.escape(elenco)}")
    if direcao_val:
        linhas.append(f"{direcao_label}: {html.escape(direcao_val)}")

    return "\n".join(linhas)

# ── Envio ──────────────────────────────────────────────────────────────────
async def enviar(context, text=None, photo=None, caption=None, markup=None, parse_mode="HTML"):
    kw = {"parse_mode": parse_mode}
    if TOPIC_ID: kw["message_thread_id"] = TOPIC_ID
    if markup:   kw["reply_markup"] = markup
    try:
        if photo:  return await context.bot.send_photo(GRUPO_ID, photo, caption=caption, **kw)
        elif text: return await context.bot.send_message(GRUPO_ID, text, **kw)
    except Exception as e:
        logging.error(f"Envio: {e}")
        kw.pop("message_thread_id", None)
        try:
            if photo:  return await context.bot.send_photo(GRUPO_ID, photo, caption=caption, **kw)
            elif text: return await context.bot.send_message(GRUPO_ID, text, **kw)
        except Exception as e2:
            logging.error(f"Fallback: {e2}")

async def send_item(context, item, is_tv=False, tipo="movie"):
    """
    Envia card completo:
      1) Foto + caption com detalhes + botão ASSISTIR e BAIXAR APP
      2) Mensagem separada com link YouTube puro → Telegram gera mini player inline
    """
    if not item: return
    iid = item.get("id")

    # Busca detalhes completos (inclui credits, videos, etc.)
    details = tmdb_details(iid, is_tv=is_tv)
    if not details: details = item  # fallback para dados básicos

    title   = details.get("name") if is_tv else details.get("title","?")
    caption = build_caption(details, is_tv=is_tv)

    # ✅ Deep link correto — abre direto no filme/série no app
    url_direto  = link_streamflix(iid, is_tv=is_tv)
    url_trailer = get_trailer_url(iid, title, is_tv=is_tv)

    # Botões: só ASSISTIR e BAIXAR APP (trailer vai como mensagem separada)
    keyboard = [
        [InlineKeyboardButton("▶️ ASSISTIR AGORA", url=url_direto)],
        [InlineKeyboardButton("💬 BAIXAR APP AQUI", url=APP_URL)]
    ]

    post = details.get("poster_path") or item.get("poster_path")
    try:
        # 1) Card principal com poster + info + botões
        if post:
            await enviar(context, photo=f"{IMG_BASE}{post}", caption=caption,
                         markup=InlineKeyboardMarkup(keyboard))
        else:
            await enviar(context, text=caption, markup=InlineKeyboardMarkup(keyboard))

        # 2) Link YouTube como texto puro → Telegram renderiza mini player inline automaticamente
        trailer_msg = "\U0001f3ac <b>Confira o Trailer:</b>\n" + url_trailer
        await enviar(context, text=trailer_msg)

        marcar(iid, tipo)
    except Exception as e:
        logging.error(e)

async def enviar_lista(context, itens, is_tv=False, tipo="movie", limite=3):
    itens = filtrar(itens, tipo)
    random.shuffle(itens)
    for item in itens[:limite]:
        await send_item(context, item, is_tv=is_tv, tipo=tipo)

# ── Handlers de texto ──────────────────────────────────────────────────────
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if update.effective_chat.id != GRUPO_ID: return

    if text == "🎥 Em Cartaz":
        d = tmdb("movie/now_playing", {"region":"BR"})
        if d: await enviar_lista(context, d.get("results",[]), tipo="now_playing")

    elif text == "🚀 Em Breve":
        d = tmdb("movie/upcoming", {"region":"BR"})
        if d: await enviar_lista(context, d.get("results",[]), tipo="upcoming")

    elif text == "🌟 Populares":
        d = tmdb("movie/popular", {"region":"BR","page":random.randint(1,5)})
        if d: await enviar_lista(context, d.get("results",[]))

    elif text == "📺 Séries":
        d = tmdb("tv/popular", {"page":random.randint(1,5)})
        if d: await enviar_lista(context, d.get("results",[]), is_tv=True, tipo="tv")

    elif text == "🔥 Em Alta":
        d = tmdb("trending/all/week")
        if d:
            for item in d.get("results",[])[:4]:
                is_tv = item.get("media_type") == "tv"
                await send_item(context, item, is_tv=is_tv, tipo="tv" if is_tv else "movie")

    elif text == "🎭 Por Gênero":
        btns = [[InlineKeyboardButton(n, callback_data=f"gen_{i}")] for n,i in GENEROS.items()]
        await enviar(context, text="✨ <b>Escolha um Gênero:</b>", markup=InlineKeyboardMarkup(btns))

    elif text == "🎞️ Por Época":
        btns = [[InlineKeyboardButton(n, callback_data=f"era_{n}")] for n in EPOCAS]
        await enviar(context, text="⏳ <b>Escolha uma Época:</b>", markup=InlineKeyboardMarkup(btns))

    elif text == "🎲 Sugestão":
        d = tmdb("movie/top_rated", {"page":random.randint(1,20)})
        if d and d.get("results"): await enviar_lista(context, d["results"], limite=1)

    elif text == "🔍 Buscar":
        await enviar(context, text=(
            "⌨️ Use os comandos:\n\n"
            "<code>/filme Nome do Filme</code>\n"
            "<code>/serie Nome da Série</code>\n"
            "<code>/ator Nome do Ator</code>\n"
            "<code>/top10</code> — Top 10 da semana"
        ))

    elif text == "❓ Ajuda":
        await cmd_ajuda_fn(context)

# ── Callback (Gênero / Época) ──────────────────────────────────────────────
async def callback_handler(update, context):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data.startswith("gen_"):
        gid = data.split("_")[1]
        d = tmdb("discover/movie", {
            "with_genres": gid, "sort_by":"popularity.desc",
            "page": random.randint(1,5)
        })
        if d and d.get("results"):
            await enviar_lista(context, d["results"])

    elif data.startswith("era_"):
        era = data.split("_",1)[1]
        inicio, fim = EPOCAS[era]
        ano = random.randint(inicio, fim)
        d = tmdb("discover/movie", {
            "primary_release_year": ano, "sort_by":"popularity.desc", "page":1
        })
        if d and d.get("results"):
            await enviar(context, text=f"🎞️ <b>Melhores de {ano}...</b>")
            await enviar_lista(context, d["results"][:10])

# ── Comandos ───────────────────────────────────────────────────────────────
async def cmd_filme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Use: /filme Nome do Filme"); return
    q = " ".join(context.args)
    d = tmdb("search/movie", {"query": q})
    res = d.get("results",[]) if d else []
    if not res:
        await enviar(context, text=f"😕 Filme não encontrado: <b>{html.escape(q)}</b>"); return
    await send_item(context, res[0], tipo="movie")

async def cmd_serie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Use: /serie Nome da Série"); return
    q = " ".join(context.args)
    d = tmdb("search/tv", {"query": q})
    res = d.get("results",[]) if d else []
    if not res:
        await enviar(context, text=f"😕 Série não encontrada: <b>{html.escape(q)}</b>"); return
    await send_item(context, res[0], is_tv=True, tipo="tv")

async def cmd_ator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Busca filmes por nome de ator/atriz."""
    if not context.args:
        await update.message.reply_text("⚠️ Use: /ator Nome do Ator"); return
    q = " ".join(context.args)
    # Busca pessoa
    d = tmdb("search/person", {"query": q})
    pessoas = d.get("results",[]) if d else []
    if not pessoas:
        await enviar(context, text=f"😕 Ator não encontrado: <b>{html.escape(q)}</b>"); return

    pessoa = pessoas[0]
    nome   = pessoa.get("name","")
    pid    = pessoa.get("id")

    # Filmes desse ator ordenados por popularidade
    filmes_d = tmdb(f"person/{pid}/movie_credits")
    filmes   = filmes_d.get("cast",[]) if filmes_d else []
    filmes   = sorted(filmes, key=lambda x: x.get("popularity",0), reverse=True)

    if not filmes:
        await enviar(context, text=f"😕 Nenhum filme encontrado para <b>{html.escape(nome)}</b>"); return

    await enviar(context, text=f"🌟 <b>Filmes de {html.escape(nome)}:</b>")
    await enviar_lista(context, filmes[:10], tipo="movie", limite=3)

async def cmd_top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia o Top 10 da semana (trending)."""
    d = tmdb("trending/all/week")
    if not d or not d.get("results"):
        await enviar(context, text="😕 Não foi possível buscar o Top 10."); return

    itens = d["results"][:10]
    linhas = ["🏆 <b>TOP 10 DA SEMANA:</b>\n"]
    for i, item in enumerate(itens, 1):
        is_tv = item.get("media_type") == "tv"
        name  = item.get("name") if is_tv else item.get("title","?")
        ano   = (item.get("first_air_date","") if is_tv else item.get("release_date",""))[:4]
        nota  = item.get("vote_average",0)
        tipo  = "📺" if is_tv else "🎬"
        iid   = item.get("id")
        url   = link_streamflix(iid, is_tv=is_tv)
        linhas.append(f"{i}. {tipo} <a href=\"{url}\">{html.escape(name)}</a> ({ano}) — ⭐{nota:.1f}")

    await enviar(context, text="\n".join(linhas))

async def cmd_avisogeral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("⚠️ /avisogeral mensagem"); return
    await enviar(context, text=msg)
    await update.message.reply_text("📢 Aviso enviado!")

async def cmd_ajuda_fn(context):
    texto = (
        "❓ <b>Comandos:</b>\n\n"
        "🎥 <b>Em Cartaz</b> — cinemas agora\n"
        "🚀 <b>Em Breve</b> — próximos lançamentos\n"
        "🌟 <b>Populares</b> — mais vistos\n"
        "📺 <b>Séries</b> — séries em alta\n"
        "🔥 <b>Em Alta</b> — trending da semana\n"
        "🎭 <b>Por Gênero</b> — filtre por estilo\n"
        "🎞️ <b>Por Época</b> — por década\n"
        "🎲 <b>Sugestão</b> — surpresa aleatória\n\n"
        "<code>/filme Nome</code> — busca filme\n"
        "<code>/serie Nome</code> — busca série\n"
        "<code>/ator Nome</code> — filmes de um ator\n"
        "<code>/top10</code> — ranking semanal\n"
    )
    await enviar(context, text=texto)

async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_ajuda_fn(context)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        c = db(); cur = c.cursor()
        cur.execute("INSERT INTO subscribed_chats VALUES(%s) ON CONFLICT DO NOTHING",
                    (update.effective_chat.id,))
        c.commit(); cur.close(); c.close()
    except: pass

    user = update.effective_user
    kb = [
        ["🎥 Em Cartaz","🚀 Em Breve"],
        ["🌟 Populares","📺 Séries"],
        ["🔥 Em Alta","🎲 Sugestão"],
        ["🎭 Por Gênero","🎞️ Por Época"],
        ["🔍 Buscar","❓ Ajuda"]
    ]
    promo = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 ACESSAR STREAMFLIX", url=SITE_URL)],
        [InlineKeyboardButton("📱 BAIXAR APP",         url=APP_URL)]
    ])
    await enviar(context,
        text=f"🎬 <b>StreamFlix Bot</b>\n\nOlá {html.escape(user.first_name)}! Pronto para assistir? 🍿",
        markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    await enviar(context, text="Acesse o StreamFlix:", markup=promo)

# ── Jobs automáticos ───────────────────────────────────────────────────────
async def job_diario_manha(context: ContextTypes.DEFAULT_TYPE):
    """Postagem automática às 8h — filmes em cartaz."""
    logging.info("⏰ Job manhã: Em Cartaz")
    d = tmdb("movie/now_playing", {"region":"BR"})
    if d:
        await enviar(context, text="🌅 <b>Bom dia! Confira o que está em cartaz hoje:</b>")
        await enviar_lista(context, d.get("results",[]), tipo="now_playing", limite=2)

async def job_diario_noite(context: ContextTypes.DEFAULT_TYPE):
    """Postagem automática às 20h — trending da semana."""
    logging.info("⏰ Job noite: Trending")
    d = tmdb("trending/all/week")
    if d:
        await enviar(context, text="🌆 <b>Boa noite! Top da semana para você:</b>")
        itens = d.get("results",[])[:6]
        random.shuffle(itens)
        for item in itens[:2]:
            is_tv = item.get("media_type") == "tv"
            await send_item(context, item, is_tv=is_tv, tipo="tv" if is_tv else "movie")

# ── Main ───────────────────────────────────────────────────────────────────
def main():
    setup_db()
    threading.Thread(target=start_health, daemon=True).start()

    app = Application.builder().token(TOKEN).build()

    # Comandos
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("ajuda",      cmd_ajuda))
    app.add_handler(CommandHandler("help",       cmd_ajuda))
    app.add_handler(CommandHandler("avisogeral", cmd_avisogeral))
    app.add_handler(CommandHandler("filme",      cmd_filme))
    app.add_handler(CommandHandler("serie",      cmd_serie))
    app.add_handler(CommandHandler("ator",       cmd_ator))
    app.add_handler(CommandHandler("top10",      cmd_top10))

    # Texto e callbacks
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Jobs automáticos (UTC — ajuste conforme fuso de Brasília = UTC-3)
    jq = app.job_queue
    if jq:
        jq.run_daily(job_diario_manha, time=datetime.strptime("11:00","%H:%M").time())   # 8h BRT
        jq.run_daily(job_diario_noite, time=datetime.strptime("23:00","%H:%M").time())   # 20h BRT

    logging.info(f"✅ Bot v7.0 Online — {SITE_URL}")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    while True:
        try: main()
        except Exception as e:
            logging.error(f"💥 Reiniciando: {e}"); time.sleep(10)
