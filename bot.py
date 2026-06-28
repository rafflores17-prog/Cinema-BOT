# ================= BOT DE CINEMA v8.0 — StreamFlix SaaS Edition =================
# Novidades v8:
#   ✅ Sistema multi-tenant (vários clientes, um bot)
#   ✅ Aluguel de 30 dias com renovação automática
#   ✅ Painel admin completo via Telegram
#   ✅ Aviso automático 3 dias antes de vencer
#   ✅ Bloqueio automático ao vencer + mensagem de renovação
#   ✅ Tokens de ativação seguros
#   ✅ Postagem automática para TODOS os clientes ativos
# =================================================================================

import os, html, time, random, logging, threading, secrets, string
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, quote
import requests, psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          filters, ContextTypes, CallbackQueryHandler)

# ── Variáveis de ambiente ──────────────────────────────────────────────────
TOKEN         = os.environ.get("TOKEN",        os.environ.get("BOT_TOKEN", ""))
TMDB_KEY      = os.environ.get("TMDB_API_KEY", "")
DATABASE_URL  = os.environ.get("DATABASE_URL", "")
SITE_URL      = os.environ.get("SITE_URL",     "https://streamflixvip.online")
APP_URL       = os.environ.get("APP_URL",      "https://streamflixvip.online")
ADMIN_ID      = int(os.environ.get("ADMIN_ID", "0"))   # Seu user_id do Telegram (não chat_id do canal)
GRUPO_ID      = int(os.environ.get("GRUPO_ID", "0"))   # Seu canal principal
TOPIC_ID      = int(os.environ.get("TOPIC_ID", "0"))
CANAL_SUPORTE = "https://t.me/streamflixofc"
DIAS_SEM_REPETIR = 21
DIAS_PLANO       = 30

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

# ── Servidor HTTP (healthcheck + API do painel) ────────────────────────────
PANEL_PASS = os.environ.get("PANEL_PASS", "")  # Senha do painel web

class AdminHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_response(200); self.send_header("Content-Type","text/plain"); self.end_headers()
            self.wfile.write(b"StreamFlix BOT OK"); return

        if parsed.path == "/admin":
            self._handle_admin(parsed); return

        self.send_response(404); self.end_headers()

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors(); self.end_headers()

    def _json(self, data, status=200):
        body = __import__('json').dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors(); self.end_headers()
        self.wfile.write(body)

    def _handle_admin(self, parsed):
        from urllib.parse import parse_qs
        params = parse_qs(parsed.query)
        pw  = params.get("pass",  [""])[0]
        cmd = params.get("cmd",   [""])[0]

        if not PANEL_PASS or pw != PANEL_PASS:
            self._json({"error": "Senha incorreta."}, 403); return

        try:
            if cmd == "stats":
                c = db(); cur = c.cursor()
                cur.execute("SELECT COUNT(*) FROM clientes WHERE ativo=TRUE AND validade > NOW()")
                ativos = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM clientes WHERE ativo=FALSE OR validade <= NOW()")
                inativos = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM tokens WHERE usado=FALSE")
                tokens_livres = cur.fetchone()[0]
                cur.close(); c.close()
                self._json({"ativos": ativos, "inativos": inativos,
                            "tokens_livres": tokens_livres,
                            "receita": f"{ativos*30:.2f}"}); return

            if cmd == "clientes":
                c = db(); cur = c.cursor()
                cur.execute("""SELECT chat_id, ativo, validade, criado_em, modo, site_url
                    FROM clientes ORDER BY criado_em DESC""")
                rows = cur.fetchall(); cur.close(); c.close()
                result = []
                for chat_id, ativo, validade, criado, modo, site_url in rows:
                    dias = (validade - datetime.utcnow()).days if validade else -1
                    result.append({
                        "chat_id": chat_id,
                        "ativo": bool(ativo and dias >= 0),
                        "validade": validade.strftime("%d/%m/%Y") if validade else None,
                        "dias_rest": dias,
                        "modo": modo or "completo",
                        "site_url": site_url or ""
                    })
                self._json({"clientes": result}); return

            if cmd.startswith("gerar:"):
                qtd = min(int(cmd.split(":")[1]), 10)
                tokens = [gerar_token() for _ in range(qtd)]
                self._json({"tokens": tokens, "ok": True}); return

            if cmd.startswith("renovar:"):
                cid = int(cmd.split(":")[1])
                nova = renovar_cliente(cid)
                self._json({"ok": nova is not None,
                            "validade": nova.strftime("%d/%m/%Y") if nova else None}); return

            if cmd.startswith("revogar:"):
                cid = int(cmd.split(":")[1])
                ok = revogar_cliente(cid)
                self._json({"ok": ok}); return

            if cmd.startswith("config_modo:"):
                _, cid, modo = cmd.split(":", 2)
                ok = set_modo(int(cid), modo)
                self._json({"ok": ok}); return

            if cmd.startswith("config_site:"):
                from urllib.parse import unquote
                _, cid, url = cmd.split(":", 2)
                url = unquote(url)
                ok = set_site_url(int(cid), None if url == "remover" else url)
                self._json({"ok": ok}); return

            if cmd.startswith("ativar:"):
                parts = cmd.split(":")
                cid   = int(parts[1])
                token = parts[2].strip().upper()
                if not token_valido(token):
                    self._json({"ok": False, "error": "Token inválido ou já usado."}); return
                validade = usar_token(token, cid)
                self._json({"ok": validade is not None,
                            "validade": validade.strftime("%d/%m/%Y") if validade else None}); return

            self._json({"error": "Comando desconhecido."}, 400)
        except Exception as e:
            logging.error(f"AdminAPI: {e}")
            self._json({"error": str(e)}, 500)

    def log_message(self, *a, **k): pass

def start_health():
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT","8000"))), AdminHandler).serve_forever()


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
        # Clientes (multi-tenant)
        cur.execute("""CREATE TABLE IF NOT EXISTS clientes (
            chat_id    BIGINT PRIMARY KEY,
            topic_id   BIGINT DEFAULT 0,
            token      TEXT,
            ativo      BOOLEAN DEFAULT TRUE,
            validade   TIMESTAMP,
            aviso_3d   BOOLEAN DEFAULT FALSE,
            aviso_venc BOOLEAN DEFAULT FALSE,
            criado_em  TIMESTAMP DEFAULT NOW(),
            modo       TEXT DEFAULT 'completo',
            site_url   TEXT DEFAULT NULL
        );""")
        # Migrações de colunas novas
        try:
            cur.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS modo TEXT DEFAULT 'completo'")
            cur.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS site_url TEXT DEFAULT NULL")
            c.commit()
        except: pass
        # Tokens gerados pelo admin
        cur.execute("""CREATE TABLE IF NOT EXISTS tokens (
            token     TEXT PRIMARY KEY,
            usado     BOOLEAN DEFAULT FALSE,
            criado_em TIMESTAMP DEFAULT NOW()
        );""")
        # Itens enviados por cliente (para não repetir)
        cur.execute("""CREATE TABLE IF NOT EXISTS sent_items (
            chat_id   BIGINT NOT NULL,
            item_id   BIGINT NOT NULL,
            item_type TEXT NOT NULL,
            sent_at   TIMESTAMP NOT NULL,
            PRIMARY KEY (chat_id, item_id, item_type)
        );""")
        c.commit(); cur.close(); c.close()
        logging.info("✅ Banco pronto (v8 SaaS)")
    except Exception as e:
        logging.error(f"Banco: {e}")

# ── Funções de cliente ─────────────────────────────────────────────────────
def gerar_token():
    chars = string.ascii_uppercase + string.digits
    token = "SF-" + "".join(secrets.choice(chars) for _ in range(10))
    try:
        c = db(); cur = c.cursor()
        cur.execute("INSERT INTO tokens (token) VALUES (%s)", (token,))
        c.commit(); cur.close(); c.close()
    except Exception as e:
        logging.error(e)
    return token

def token_valido(token):
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT token FROM tokens WHERE token=%s AND usado=FALSE", (token,))
        r = cur.fetchone(); cur.close(); c.close()
        return r is not None
    except: return False

def usar_token(token, chat_id, topic_id=0):
    try:
        c = db(); cur = c.cursor()
        validade = datetime.utcnow() + timedelta(days=DIAS_PLANO)
        cur.execute("""INSERT INTO clientes (chat_id, topic_id, token, ativo, validade)
            VALUES (%s,%s,%s,TRUE,%s)
            ON CONFLICT (chat_id) DO UPDATE
            SET token=%s, ativo=TRUE, validade=%s, aviso_3d=FALSE, aviso_venc=FALSE""",
            (chat_id, topic_id, token, validade, token, validade))
        cur.execute("UPDATE tokens SET usado=TRUE WHERE token=%s", (token,))
        c.commit(); cur.close(); c.close()
        return validade
    except Exception as e:
        logging.error(e); return None

def cliente_ativo(chat_id):
    if chat_id == GRUPO_ID: return True  # canal do dono sempre liberado
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT ativo, validade FROM clientes WHERE chat_id=%s", (chat_id,))
        r = cur.fetchone(); cur.close(); c.close()
        if not r: return False
        ativo, validade = r
        if not ativo: return False
        if validade and datetime.utcnow() > validade: return False
        return True
    except: return False

def get_topic_id(chat_id):
    if chat_id == GRUPO_ID: return TOPIC_ID
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT topic_id FROM clientes WHERE chat_id=%s", (chat_id,))
        r = cur.fetchone(); cur.close(); c.close()
        return r[0] if r else 0
    except: return 0

def listar_clientes():
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT chat_id, ativo, validade, criado_em FROM clientes ORDER BY criado_em DESC")
        rows = cur.fetchall(); cur.close(); c.close()
        return rows
    except: return []

def renovar_cliente(chat_id):
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT validade FROM clientes WHERE chat_id=%s", (chat_id,))
        r = cur.fetchone()
        if not r: return None
        base = max(r[0], datetime.utcnow()) if r[0] else datetime.utcnow()
        nova = base + timedelta(days=DIAS_PLANO)
        cur.execute("""UPDATE clientes SET ativo=TRUE, validade=%s,
            aviso_3d=FALSE, aviso_venc=FALSE WHERE chat_id=%s""", (nova, chat_id))
        c.commit(); cur.close(); c.close()
        return nova
    except Exception as e:
        logging.error(e); return None

def revogar_cliente(chat_id):
    try:
        c = db(); cur = c.cursor()
        cur.execute("UPDATE clientes SET ativo=FALSE WHERE chat_id=%s", (chat_id,))
        c.commit(); cur.close(); c.close()
        return True
    except: return False

def get_modo(chat_id):
    """Retorna o modo do cliente: 'completo' (padrão) ou 'simples'."""
    if chat_id == GRUPO_ID: return "completo"
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT modo FROM clientes WHERE chat_id=%s", (chat_id,))
        r = cur.fetchone(); cur.close(); c.close()
        return (r[0] if r and r[0] else "completo")
    except: return "completo"

def set_modo(chat_id, modo):
    """Define modo 'completo' ou 'simples' para um cliente."""
    try:
        c = db(); cur = c.cursor()
        cur.execute("UPDATE clientes SET modo=%s WHERE chat_id=%s", (modo, chat_id))
        c.commit(); cur.close(); c.close()
        return True
    except Exception as e:
        logging.error(e); return False

def get_site_url(chat_id):
    """Retorna o site_url personalizado do cliente, ou o SITE_URL padrão."""
    if chat_id == GRUPO_ID: return SITE_URL
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT site_url FROM clientes WHERE chat_id=%s", (chat_id,))
        r = cur.fetchone(); cur.close(); c.close()
        return (r[0] if r and r[0] else SITE_URL)
    except: return SITE_URL

def set_site_url(chat_id, url):
    try:
        c = db(); cur = c.cursor()
        cur.execute("UPDATE clientes SET site_url=%s WHERE chat_id=%s", (url or None, chat_id))
        c.commit(); cur.close(); c.close()
        return True
    except Exception as e:
        logging.error(e); return False


    try:
        c = db(); cur = c.cursor()
        limite = datetime.utcnow() + timedelta(days=3)
        cur.execute("""SELECT chat_id FROM clientes
            WHERE ativo=TRUE AND validade <= %s AND aviso_3d=FALSE""", (limite,))
        rows = [r[0] for r in cur.fetchall()]; cur.close(); c.close()
        return rows
    except: return []

def clientes_vencidos():
    try:
        c = db(); cur = c.cursor()
        cur.execute("""SELECT chat_id FROM clientes
            WHERE ativo=TRUE AND validade < NOW() AND aviso_venc=FALSE""")
        rows = [r[0] for r in cur.fetchall()]; cur.close(); c.close()
        return rows
    except: return []

def marcar_aviso_3d(chat_id):
    try:
        c = db(); cur = c.cursor()
        cur.execute("UPDATE clientes SET aviso_3d=TRUE WHERE chat_id=%s", (chat_id,))
        c.commit(); cur.close(); c.close()
    except: pass

def marcar_vencido(chat_id):
    try:
        c = db(); cur = c.cursor()
        cur.execute("UPDATE clientes SET ativo=FALSE, aviso_venc=TRUE WHERE chat_id=%s", (chat_id,))
        c.commit(); cur.close(); c.close()
    except: pass

# ── TMDB ───────────────────────────────────────────────────────────────────
def tmdb(endpoint, params=None):
    p = {"api_key": TMDB_KEY, "language": "pt-BR", **(params or {})}
    for _ in range(2):
        try:
            r = requests.get(f"{TMDB_BASE}/{endpoint}", params=p, timeout=15)
            r.raise_for_status(); return r.json()
        except Exception as e:
            logging.warning(e); time.sleep(1)
    return None

def tmdb_details(item_id, is_tv=False):
    tipo = "tv" if is_tv else "movie"
    return tmdb(f"{tipo}/{item_id}", {"append_to_response": "credits,videos"})

def get_trailer_url(item_id, titulo, is_tv=False):
    v = tmdb(f"{'tv' if is_tv else 'movie'}/{item_id}/videos")
    if v and v.get("results"):
        res = v["results"]
        t = next((x for x in res if x["type"]=="Trailer" and x["site"]=="YouTube"), None)
        if t: return f"https://youtu.be/{t['key']}"
        yt = next((x for x in res if x["site"]=="YouTube"), None)
        if yt: return f"https://youtu.be/{yt['key']}"
    return f"https://www.youtube.com/results?search_query={quote(titulo+' Trailer Oficial')}"

def link_streamflix(item_id, is_tv=False):
    return f"{SITE_URL}/#/title/{item_id}/{'tv' if is_tv else 'movie'}"

def formatar_estrelas(rating):
    if not rating: return "—"
    cheias = round(rating / 2)
    return "⭐" * cheias + "☆" * (5 - cheias)

def formatar_runtime(minutos):
    if not minutos: return ""
    h, m = divmod(minutos, 60)
    if h and m: return f"{h}h{m:02d}min"
    if h: return f"{h}h"
    return f"{m}min"

def build_caption(details, is_tv=False):
    if not details: return "ℹ️ Informações indisponíveis."
    titulo     = details.get("name") if is_tv else details.get("title","?")
    orig_title = details.get("original_name" if is_tv else "original_title","")
    ano        = (details.get("first_air_date","") if is_tv else details.get("release_date",""))[:4] or "?"
    rating     = details.get("vote_average", 0)
    count      = details.get("vote_count", 0)
    sinopse    = details.get("overview") or "Sinopse não disponível."
    if len(sinopse) > 300: sinopse = sinopse[:300].rsplit(" ",1)[0] + "…"
    gen_list   = [g["name"] for g in details.get("genres", [])]
    generos    = " • ".join(gen_list[:3]) if gen_list else ""
    if is_tv:
        seasons  = details.get("number_of_seasons", 0)
        episodes = details.get("number_of_episodes", 0)
        duracao  = f"📺 {seasons} temp. • {episodes} eps." if seasons else ""
        status_map = {
            "Returning Series":"🟢 Em exibição","Ended":"🔴 Encerrada",
            "Canceled":"⛔ Cancelada","In Production":"🎬 Em produção"
        }
        status = status_map.get(details.get("status",""), "")
    else:
        runtime = details.get("runtime") or 0
        duracao = f"⏱ {formatar_runtime(runtime)}" if runtime else ""
        status  = ""
    credits   = details.get("credits", {})
    cast_list = [p.get("name","") for p in credits.get("cast", [])[:5]]
    elenco    = ", ".join(cast_list) if cast_list else ""
    if is_tv:
        criadores = [c.get("name","") for c in details.get("created_by", [])]
        dir_label = "✍️ Criado por"; dir_val = ", ".join(criadores[:2]) if criadores else ""
    else:
        diretores = [p["name"] for p in credits.get("crew",[]) if p.get("job")=="Director"]
        dir_label = "🎬 Direção"; dir_val = ", ".join(diretores[:2]) if diretores else ""
    icone  = "📺" if is_tv else "🎬"
    linhas = [f"{icone} <b>{html.escape(titulo)}</b> ({ano})"]
    if orig_title and orig_title != titulo: linhas.append(f"<i>{html.escape(orig_title)}</i>")
    linhas += ["", f"{formatar_estrelas(rating)} <b>{rating:.1f}/10</b> ({count:,} votos)"]
    if generos: linhas.append(f"🎭 {html.escape(generos)}")
    if duracao: linhas.append(duracao)
    if status:  linhas.append(status)
    linhas += ["", f"📖 {html.escape(sinopse)}"]
    if elenco:   linhas += ["", f"🌟 <b>Elenco:</b> {html.escape(elenco)}"]
    if dir_val:  linhas.append(f"{dir_label}: {html.escape(dir_val)}")
    return "\n".join(linhas)

# ── Itens enviados por cliente ─────────────────────────────────────────────
def ja_enviados(chat_id, tipo):
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT item_id FROM sent_items WHERE chat_id=%s AND item_type=%s AND sent_at>%s",
                    (chat_id, tipo, datetime.utcnow()-timedelta(days=DIAS_SEM_REPETIR)))
        ids = {r[0] for r in cur.fetchall()}; cur.close(); c.close()
        return ids
    except: return set()

def marcar_enviado(chat_id, item_id, tipo):
    try:
        c = db(); cur = c.cursor()
        cur.execute("""INSERT INTO sent_items VALUES(%s,%s,%s,%s)
            ON CONFLICT(chat_id,item_id,item_type) DO UPDATE SET sent_at=EXCLUDED.sent_at""",
            (chat_id, item_id, tipo, datetime.utcnow()))
        c.commit(); cur.close(); c.close()
    except Exception as e: logging.error(e)

def filtrar(chat_id, itens, tipo):
    env   = ja_enviados(chat_id, tipo)
    novos = [i for i in itens if i.get("id") not in env]
    return novos if novos else itens

# ── Envio ──────────────────────────────────────────────────────────────────
async def enviar(context, chat_id, text=None, photo=None, caption=None, markup=None, parse_mode="HTML"):
    topic = get_topic_id(chat_id)
    kw = {"parse_mode": parse_mode}
    if topic:  kw["message_thread_id"] = topic
    if markup: kw["reply_markup"] = markup
    try:
        if photo:  return await context.bot.send_photo(chat_id, photo, caption=caption, **kw)
        elif text: return await context.bot.send_message(chat_id, text, **kw)
    except Exception as e:
        logging.error(f"Envio: {e}")
        kw.pop("message_thread_id", None)
        try:
            if photo:  return await context.bot.send_photo(chat_id, photo, caption=caption, **kw)
            elif text: return await context.bot.send_message(chat_id, text, **kw)
        except Exception as e2: logging.error(f"Fallback: {e2}")

async def send_item(context, chat_id, item, is_tv=False, tipo="movie"):
    if not item: return
    iid     = item.get("id")
    details = tmdb_details(iid, is_tv=is_tv) or item
    title   = details.get("name") if is_tv else details.get("title","?")
    caption = build_caption(details, is_tv=is_tv)
    modo     = get_modo(chat_id)
    site     = get_site_url(chat_id)
    # modo 'completo': botão site personalizado; modo 'simples': só assistir
    if modo == "simples":
        keyboard = [
            [InlineKeyboardButton("▶️ ASSISTIR AGORA", url=link_streamflix(iid, is_tv=is_tv))]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("▶️ ASSISTIR AGORA",    url=link_streamflix(iid, is_tv=is_tv))],
            [InlineKeyboardButton("🌐 Visite nosso Site", url=site)]
        ]
    post = details.get("poster_path") or item.get("poster_path")
    try:
        if post: await enviar(context, chat_id, photo=f"{IMG_BASE}{post}", caption=caption, markup=InlineKeyboardMarkup(keyboard))
        else:    await enviar(context, chat_id, text=caption, markup=InlineKeyboardMarkup(keyboard))
        await enviar(context, chat_id, text=f"🎬 <b>Confira o Trailer:</b>\n{get_trailer_url(iid, title, is_tv=is_tv)}")
        marcar_enviado(chat_id, iid, tipo)
    except Exception as e: logging.error(e)

async def enviar_lista(context, chat_id, itens, is_tv=False, tipo="movie", limite=3):
    itens = filtrar(chat_id, itens, tipo)
    random.shuffle(itens)
    for item in itens[:limite]:
        await send_item(context, chat_id, item, is_tv=is_tv, tipo=tipo)

# ── Verificação de acesso ──────────────────────────────────────────────────
async def verificar_acesso(update: Update, context) -> bool:
    cid = update.effective_chat.id
    if cliente_ativo(cid): return True
    await update.message.reply_text(
        "🔒 <b>Acesso bloqueado!</b>\n\n"
        "Seu plano não está ativo ou expirou.\n\n"
        f"Para ativar ou renovar:\n{CANAL_SUPORTE}",
        parse_mode="HTML"
    )
    return False

# ── Comandos de cliente ────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    user = update.effective_user
    if not cliente_ativo(cid):
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
        await update.message.reply_text(
            f"👋 Olá <b>{html.escape(user.first_name)}</b>! Bem-vindo ao StreamFlix Bot! 🎬\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 <b>COMO CONFIGURAR O BOT NO SEU CANAL</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>1️⃣ Adquira seu plano:</b>\n"
            f"👉 {CANAL_SUPORTE}\n\n"
            f"<b>2️⃣ Adicione o bot ao seu canal:</b>\n"
            f"• Abra seu canal no Telegram\n"
            f"• Toque nos 3 pontos (⋮) no canto superior\n"
            f"• Vá em <b>Administradores</b>\n"
            f"• Toque em <b>Adicionar Administrador</b>\n"
            f"• Pesquise: <code>@{bot_username}</code>\n"
            f"• Ative a permissão <b>Enviar Mensagens</b> ✅\n"
            f"• Confirme\n\n"
            f"<b>3️⃣ Ative seu plano no canal:</b>\n"
            f"Digite no seu canal:\n"
            f"<code>/ativar SEU_TOKEN</code>\n\n"
            f"<b>4️⃣ Tudo pronto! 🚀</b>\n"
            f"O bot já começa a postar automaticamente!\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"❓ Dúvidas? {CANAL_SUPORTE}",
            parse_mode="HTML"
        )
        return
    kb = [
        ["🎥 Em Cartaz","🚀 Em Breve"],
        ["🌟 Populares","📺 Séries"],
        ["🔥 Em Alta","🎲 Sugestão"],
        ["🎭 Por Gênero","🎞️ Por Época"],
        ["🔍 Buscar","❓ Ajuda"]
    ]
    promo = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Visite nosso Site", url=SITE_URL)]
    ])
    await enviar(context, cid,
        text=f"🎬 <b>StreamFlix Bot</b>\n\nOlá {html.escape(user.first_name)}! Pronto para assistir? 🍿",
        markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    await enviar(context, cid, text="✨ Acesse agora:", markup=promo)

async def cmd_ativar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("⚠️ Use: <code>/ativar SEU_TOKEN</code>", parse_mode="HTML")
        return
    token = context.args[0].strip().upper()
    if not token_valido(token):
        await update.message.reply_text(
            "❌ Token inválido ou já utilizado.\n\nAdquira um novo em: " + CANAL_SUPORTE)
        return
    topic    = int(context.args[1]) if len(context.args) > 1 else 0
    validade = usar_token(token, cid, topic)
    if validade:
        await update.message.reply_text(
            f"✅ <b>Bot ativado com sucesso!</b>\n\n"
            f"📅 Válido até: <b>{validade.strftime('%d/%m/%Y')}</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🚀 <b>PRÓXIMOS PASSOS:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"O bot já está ativo neste canal! Agora:\n\n"
            f"▶️ Use /start para abrir o menu\n"
            f"🎥 Use os botões para buscar filmes e séries\n"
            f"⏰ Posts automáticos chegam todo dia às 8h e 20h\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 <b>COMANDOS DISPONÍVEIS:</b>\n"
            f"/filme Nome — busca um filme\n"
            f"/serie Nome — busca uma série\n"
            f"/ator Nome — filmes de um ator\n"
            f"/top10 — top 10 da semana\n"
            f"/meuplano — ver validade do plano\n\n"
            f"❓ Suporte: {CANAL_SUPORTE}",
            parse_mode="HTML"
        )
        # Avisa o admin
        try:
            await context.bot.send_message(ADMIN_ID,
                f"🟢 Novo cliente ativado!\nChat ID: <code>{cid}</code>\nToken: <code>{token}</code>\nVálido até: {validade.strftime('%d/%m/%Y')}",
                parse_mode="HTML")
        except: pass
    else:
        await update.message.reply_text("❌ Erro ao ativar. Contate: " + CANAL_SUPORTE)

async def cmd_meuplan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT ativo, validade FROM clientes WHERE chat_id=%s", (cid,))
        r = cur.fetchone(); cur.close(); c.close()
    except: r = None
    if not r:
        await update.message.reply_text(f"❌ Sem plano ativo.\nAdquira em: {CANAL_SUPORTE}")
        return
    ativo, validade = r
    dias_rest = (validade - datetime.utcnow()).days if validade else 0
    status    = "✅ Ativo" if (ativo and dias_rest > 0) else "❌ Expirado"
    await update.message.reply_text(
        f"📋 <b>Seu Plano:</b>\n\n"
        f"Status: {status}\n"
        f"📅 Vence em: <b>{validade.strftime('%d/%m/%Y') if validade else '—'}</b>\n"
        f"⏳ Dias restantes: <b>{max(dias_rest, 0)}</b>\n\n"
        f"Para renovar: {CANAL_SUPORTE}",
        parse_mode="HTML"
    )

# ── Painel Admin ───────────────────────────────────────────────────────────
def is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_ID

async def cmd_gerar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Acesso negado."); return
    qtd    = min(int(context.args[0]) if context.args else 1, 10)
    tokens = [gerar_token() for _ in range(qtd)]
    msg    = f"🎟️ <b>{qtd} Token(s) gerado(s) — 30 dias:</b>\n\n"
    for t in tokens: msg += f"<code>{t}</code>\n"
    msg += f"\n📲 Cliente usa: <code>/ativar TOKEN</code>"
    await update.message.reply_text(msg, parse_mode="HTML")

async def cmd_clientes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Acesso negado."); return
    rows = listar_clientes()
    if not rows:
        await update.message.reply_text("📭 Nenhum cliente cadastrado."); return
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT chat_id, modo, site_url FROM clientes")
        extras = {r[0]: (r[1] or "completo", r[2]) for r in cur.fetchall()}
        cur.close(); c.close()
    except: extras = {}
    msg = f"👥 <b>Clientes ({len(rows)}):</b>\n\n"
    for chat_id, ativo, validade, criado in rows:
        dias = (validade - datetime.utcnow()).days if validade else 0
        icone = "🟢" if (ativo and dias > 3) else ("🟡" if (ativo and 0 < dias <= 3) else "🔴")
        venc  = validade.strftime('%d/%m/%Y') if validade else "—"
        modo, site = extras.get(chat_id, ("completo", None))
        modo_icone = "📋" if modo == "simples" else "🌐"
        site_txt = f"\n    🔗 {site}" if site else ""
        msg  += f"{icone} <code>{chat_id}</code> — vence {venc} ({max(dias,0)}d) {modo_icone}{modo}{site_txt}\n"
    await update.message.reply_text(msg, parse_mode="HTML")

async def cmd_renovar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Acesso negado."); return
    if not context.args:
        await update.message.reply_text("⚠️ Use: /renovar CHAT_ID"); return
    cid  = int(context.args[0])
    nova = renovar_cliente(cid)
    if nova:
        await update.message.reply_text(
            f"✅ Cliente <code>{cid}</code> renovado!\nNova validade: <b>{nova.strftime('%d/%m/%Y')}</b>",
            parse_mode="HTML")
        try:
            await context.bot.send_message(cid,
                f"✅ <b>Plano renovado!</b>\n\nSeu acesso foi renovado até <b>{nova.strftime('%d/%m/%Y')}</b>.\n\nObrigado! 🎬",
                parse_mode="HTML")
        except: pass
    else:
        await update.message.reply_text(f"❌ Cliente {cid} não encontrado.")

async def cmd_revogar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Acesso negado."); return
    if not context.args:
        await update.message.reply_text("⚠️ Use: /revogar CHAT_ID"); return
    cid = int(context.args[0])
    if revogar_cliente(cid):
        await update.message.reply_text(f"✅ Acesso de <code>{cid}</code> revogado.", parse_mode="HTML")
        try:
            await context.bot.send_message(cid,
                f"⚠️ Seu acesso foi cancelado.\n\nPara reativar: {CANAL_SUPORTE}")
        except: pass
    else:
        await update.message.reply_text("❌ Erro ao revogar.")

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Acesso negado."); return
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT COUNT(*) FROM clientes WHERE ativo=TRUE AND validade > NOW()")
        ativos = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM clientes WHERE ativo=FALSE OR validade <= NOW()")
        inativos = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM tokens WHERE usado=FALSE")
        tokens_livres = cur.fetchone()[0]
        cur.close(); c.close()
    except: ativos = inativos = tokens_livres = 0
    await update.message.reply_text(
        f"📊 <b>Painel StreamFlix:</b>\n\n"
        f"🟢 Clientes ativos: <b>{ativos}</b>\n"
        f"🔴 Inativos/expirados: <b>{inativos}</b>\n"
        f"🎟️ Tokens disponíveis: <b>{tokens_livres}</b>\n\n"
        f"💰 Receita estimada: <b>R$ {ativos * 30:.2f}/mês</b>",
        parse_mode="HTML"
    )

async def cmd_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Acesso negado."); return
    # /config CHAT_ID modo simples|completo
    # /config CHAT_ID site https://...
    # /config CHAT_ID site remover
    if len(context.args) < 3:
        await update.message.reply_text(
            "⚠️ <b>Uso do /config:</b>\n\n"
            "<b>Modo de postagem:</b>\n"
            "<code>/config CHAT_ID modo completo</code> — com botão de site\n"
            "<code>/config CHAT_ID modo simples</code>  — só botão assistir\n\n"
            "<b>Site personalizado do cliente:</b>\n"
            "<code>/config CHAT_ID site https://sitedomeucliente.com</code>\n"
            "<code>/config CHAT_ID site remover</code> — volta ao padrão",
            parse_mode="HTML"); return
    try: cid = int(context.args[0])
    except:
        await update.message.reply_text("❌ CHAT_ID inválido."); return
    acao = context.args[1].lower()
    valor = context.args[2]

    if acao == "modo":
        if valor not in ("simples", "completo"):
            await update.message.reply_text("❌ Modo inválido. Use <code>simples</code> ou <code>completo</code>.", parse_mode="HTML"); return
        if set_modo(cid, valor):
            icone = "📋" if valor == "simples" else "🌐"
            await update.message.reply_text(
                f"✅ <b>Modo atualizado!</b>\n{icone} Chat <code>{cid}</code> → modo <b>{valor}</b>",
                parse_mode="HTML")
        else:
            await update.message.reply_text(f"❌ Chat ID <code>{cid}</code> não encontrado.", parse_mode="HTML")

    elif acao == "site":
        if valor.lower() == "remover":
            set_site_url(cid, None)
            await update.message.reply_text(
                f"✅ Site removido! Chat <code>{cid}</code> voltou ao padrão (<code>{SITE_URL}</code>)",
                parse_mode="HTML")
        elif valor.startswith("http"):
            if set_site_url(cid, valor):
                await update.message.reply_text(
                    f"✅ <b>Site atualizado!</b>\n🔗 Chat <code>{cid}</code> → <code>{valor}</code>",
                    parse_mode="HTML")
            else:
                await update.message.reply_text(f"❌ Chat ID <code>{cid}</code> não encontrado.", parse_mode="HTML")
        else:
            await update.message.reply_text("❌ URL inválida. Deve começar com <code>http</code>.", parse_mode="HTML")
    else:
        await update.message.reply_text("❌ Ação inválida. Use <code>modo</code> ou <code>site</code>.", parse_mode="HTML")


async def job_verificar_vencimentos(context: ContextTypes.DEFAULT_TYPE):
    """Roda a cada hora: avisa quem vence em 3 dias e bloqueia quem venceu."""
    for cid in clientes_para_avisar():
        try:
            await context.bot.send_message(cid,
                f"⚠️ <b>Seu plano vence em 3 dias!</b>\n\n"
                f"Renove agora para continuar assistindo:\n{CANAL_SUPORTE}",
                parse_mode="HTML")
            marcar_aviso_3d(cid)
            await context.bot.send_message(ADMIN_ID,
                f"🟡 Aviso enviado → <code>{cid}</code> (vence em 3 dias)", parse_mode="HTML")
        except Exception as e: logging.error(f"Aviso 3d {cid}: {e}")

    for cid in clientes_vencidos():
        try:
            marcar_vencido(cid)
            await context.bot.send_message(cid,
                f"🔴 <b>Seu plano expirou!</b>\n\n"
                f"O bot foi suspenso automaticamente.\n\n"
                f"Para renovar e reativar:\n{CANAL_SUPORTE}",
                parse_mode="HTML")
            await context.bot.send_message(ADMIN_ID,
                f"🔴 Cliente <code>{cid}</code> bloqueado automaticamente (plano vencido).", parse_mode="HTML")
        except Exception as e: logging.error(f"Bloqueio {cid}: {e}")

async def job_diario_todos(context: ContextTypes.DEFAULT_TYPE, turno="manha"):
    """Posta conteúdo para TODOS os clientes ativos."""
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT chat_id FROM clientes WHERE ativo=TRUE AND validade > NOW()")
        chats = [r[0] for r in cur.fetchall()]; cur.close(); c.close()
    except: chats = []
    if GRUPO_ID and GRUPO_ID not in chats: chats.append(GRUPO_ID)

    for cid in chats:
        try:
            if turno == "manha":
                d = tmdb("movie/now_playing", {"region":"BR"})
                if d:
                    await enviar(context, cid, text="🌅 <b>Bom dia! Confira o que está em cartaz hoje:</b>")
                    await enviar_lista(context, cid, d.get("results",[]), tipo="now_playing", limite=2)
            else:
                d = tmdb("trending/all/week")
                if d:
                    await enviar(context, cid, text="🌆 <b>Boa noite! Top da semana para você:</b>")
                    itens = d.get("results",[])[:6]; random.shuffle(itens)
                    for item in itens[:2]:
                        is_tv = item.get("media_type") == "tv"
                        await send_item(context, cid, item, is_tv=is_tv, tipo="tv" if is_tv else "movie")
        except Exception as e: logging.error(f"Job {turno} → {cid}: {e}")

async def job_diario_manha(context): await job_diario_todos(context, "manha")
async def job_diario_noite(context): await job_diario_todos(context, "noite")

# ── Handlers de texto ──────────────────────────────────────────────────────
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verificar_acesso(update, context): return
    cid  = update.effective_chat.id
    text = update.message.text

    if text == "🎥 Em Cartaz":
        d = tmdb("movie/now_playing", {"region":"BR"})
        if d: await enviar_lista(context, cid, d.get("results",[]), tipo="now_playing")

    elif text == "🚀 Em Breve":
        d = tmdb("movie/upcoming", {"region":"BR"})
        if d: await enviar_lista(context, cid, d.get("results",[]), tipo="upcoming")

    elif text == "🌟 Populares":
        d = tmdb("movie/popular", {"region":"BR","page":random.randint(1,5)})
        if d: await enviar_lista(context, cid, d.get("results",[]))

    elif text == "📺 Séries":
        d = tmdb("tv/popular", {"page":random.randint(1,5)})
        if d: await enviar_lista(context, cid, d.get("results",[]), is_tv=True, tipo="tv")

    elif text == "🔥 Em Alta":
        d = tmdb("trending/all/week")
        if d:
            for item in d.get("results",[])[:4]:
                is_tv = item.get("media_type") == "tv"
                await send_item(context, cid, item, is_tv=is_tv, tipo="tv" if is_tv else "movie")

    elif text == "🎭 Por Gênero":
        btns = [[InlineKeyboardButton(n, callback_data=f"gen_{i}")] for n,i in GENEROS.items()]
        await enviar(context, cid, text="✨ <b>Escolha um Gênero:</b>", markup=InlineKeyboardMarkup(btns))

    elif text == "🎞️ Por Época":
        btns = [[InlineKeyboardButton(n, callback_data=f"era_{n}")] for n in EPOCAS]
        await enviar(context, cid, text="⏳ <b>Escolha uma Época:</b>", markup=InlineKeyboardMarkup(btns))

    elif text == "🎲 Sugestão":
        d = tmdb("movie/top_rated", {"page":random.randint(1,20)})
        if d and d.get("results"): await enviar_lista(context, cid, d["results"], limite=1)

    elif text == "🔍 Buscar":
        await enviar(context, cid, text=(
            "⌨️ Use os comandos:\n\n"
            "<code>/filme Nome do Filme</code>\n"
            "<code>/serie Nome da Série</code>\n"
            "<code>/ator Nome do Ator</code>\n"
            "<code>/top10</code> — Top 10 da semana"
        ))

    elif text == "❓ Ajuda":
        await cmd_ajuda_fn(context, cid)

async def callback_handler(update, context):
    q   = update.callback_query; await q.answer()
    cid = update.effective_chat.id
    if not cliente_ativo(cid):
        await q.message.reply_text(f"🔒 Acesso bloqueado. Renove em: {CANAL_SUPORTE}"); return
    data = q.data

    if data.startswith("gen_"):
        gid = data.split("_")[1]
        d = tmdb("discover/movie", {"with_genres":gid,"sort_by":"popularity.desc","page":random.randint(1,5)})
        if d and d.get("results"): await enviar_lista(context, cid, d["results"])

    elif data.startswith("era_"):
        era = data.split("_",1)[1]
        inicio, fim = EPOCAS[era]
        ano = random.randint(inicio, fim)
        d = tmdb("discover/movie", {"primary_release_year":ano,"sort_by":"popularity.desc","page":1})
        if d and d.get("results"):
            await enviar(context, cid, text=f"🎞️ <b>Melhores de {ano}...</b>")
            await enviar_lista(context, cid, d["results"][:10])

# ── Comandos com verificação de acesso ────────────────────────────────────
async def cmd_filme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verificar_acesso(update, context): return
    if not context.args:
        await update.message.reply_text("⚠️ Use: /filme Nome do Filme"); return
    cid = update.effective_chat.id
    q   = " ".join(context.args)
    d   = tmdb("search/movie", {"query": q})
    res = d.get("results",[]) if d else []
    if not res:
        await enviar(context, cid, text=f"😕 Filme não encontrado: <b>{html.escape(q)}</b>"); return
    await send_item(context, cid, res[0], tipo="movie")

async def cmd_serie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verificar_acesso(update, context): return
    if not context.args:
        await update.message.reply_text("⚠️ Use: /serie Nome da Série"); return
    cid = update.effective_chat.id
    q   = " ".join(context.args)
    d   = tmdb("search/tv", {"query": q})
    res = d.get("results",[]) if d else []
    if not res:
        await enviar(context, cid, text=f"😕 Série não encontrada: <b>{html.escape(q)}</b>"); return
    await send_item(context, cid, res[0], is_tv=True, tipo="tv")

async def cmd_ator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verificar_acesso(update, context): return
    if not context.args:
        await update.message.reply_text("⚠️ Use: /ator Nome do Ator"); return
    cid = update.effective_chat.id
    q   = " ".join(context.args)
    d   = tmdb("search/person", {"query": q})
    pessoas = d.get("results",[]) if d else []
    if not pessoas:
        await enviar(context, cid, text=f"😕 Ator não encontrado: <b>{html.escape(q)}</b>"); return
    pessoa   = pessoas[0]; nome = pessoa.get("name",""); pid = pessoa.get("id")
    filmes_d = tmdb(f"person/{pid}/movie_credits")
    filmes   = sorted(filmes_d.get("cast",[]) if filmes_d else [], key=lambda x: x.get("popularity",0), reverse=True)
    if not filmes:
        await enviar(context, cid, text=f"😕 Nenhum filme encontrado para <b>{html.escape(nome)}</b>"); return
    await enviar(context, cid, text=f"🌟 <b>Filmes de {html.escape(nome)}:</b>")
    await enviar_lista(context, cid, filmes[:10], tipo="movie", limite=3)

async def cmd_top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verificar_acesso(update, context): return
    cid = update.effective_chat.id
    d   = tmdb("trending/all/week")
    if not d or not d.get("results"):
        await enviar(context, cid, text="😕 Não foi possível buscar o Top 10."); return
    itens  = d["results"][:10]
    linhas = ["🏆 <b>TOP 10 DA SEMANA:</b>\n"]
    for i, item in enumerate(itens, 1):
        is_tv = item.get("media_type") == "tv"
        name  = item.get("name") if is_tv else item.get("title","?")
        ano   = (item.get("first_air_date","") if is_tv else item.get("release_date",""))[:4]
        nota  = item.get("vote_average",0)
        tipo  = "📺" if is_tv else "🎬"
        url   = link_streamflix(item.get("id"), is_tv=is_tv)
        linhas.append(f"{i}. {tipo} <a href=\"{url}\">{html.escape(name)}</a> ({ano}) — ⭐{nota:.1f}")
    await enviar(context, cid, text="\n".join(linhas))

async def cmd_ajuda_fn(context, cid):
    await enviar(context, cid, text=(
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
        "<code>/meuplano</code> — ver seu plano\n"
    ))

async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verificar_acesso(update, context): return
    await cmd_ajuda_fn(context, update.effective_chat.id)

# ── Main ───────────────────────────────────────────────────────────────────
def main():
    setup_db()
    threading.Thread(target=start_health, daemon=True).start()
    app = Application.builder().token(TOKEN).build()

    # Comandos de cliente
    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("ativar",   cmd_ativar))
    app.add_handler(CommandHandler("meuplano", cmd_meuplan))
    app.add_handler(CommandHandler("ajuda",    cmd_ajuda))
    app.add_handler(CommandHandler("help",     cmd_ajuda))
    app.add_handler(CommandHandler("filme",    cmd_filme))
    app.add_handler(CommandHandler("serie",    cmd_serie))
    app.add_handler(CommandHandler("ator",     cmd_ator))
    app.add_handler(CommandHandler("top10",    cmd_top10))

    # Painel admin (só você usa — protegido por ADMIN_ID)
    app.add_handler(CommandHandler("gerar",    cmd_gerar))
    app.add_handler(CommandHandler("clientes", cmd_clientes))
    app.add_handler(CommandHandler("renovar",  cmd_renovar))
    app.add_handler(CommandHandler("revogar",  cmd_revogar))
    app.add_handler(CommandHandler("stats",    cmd_stats))
    app.add_handler(CommandHandler("config",   cmd_config))

    # Texto e callbacks
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Jobs automáticos
    jq = app.job_queue
    if jq:
        jq.run_daily(job_diario_manha,           time=datetime.strptime("11:00","%H:%M").time())  # 8h BRT
        jq.run_daily(job_diario_noite,           time=datetime.strptime("23:00","%H:%M").time())  # 20h BRT
        jq.run_repeating(job_verificar_vencimentos, interval=3600, first=60)                       # a cada 1h

    logging.info(f"✅ Bot v8.0 SaaS Online — {SITE_URL}")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    while True:
        try: main()
        except Exception as e:
            logging.error(f"💥 Reiniciando: {e}"); time.sleep(10)
