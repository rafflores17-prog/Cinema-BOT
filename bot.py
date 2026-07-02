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
GRUPO_ID      = int(os.environ.get("GRUPO_ID", "0"))   # Seu canal principal (streamflixofc)
CANAL_VIP     = int(os.environ.get("CANAL_VIP", "0"))    # Canal VIP (streamflixvip)
ADMIN_CONTATO = os.environ.get("ADMIN_CONTATO", "@RaffDimitri")  # Contato para propagandas
TOPIC_ID      = int(os.environ.get("TOPIC_ID", "0"))
CANAL_SUPORTE = "https://t.me/streamflixofc"
MP_TOKEN      = os.environ.get("MP_ACCESS_TOKEN", "")  # Mercado Pago Access Token
BOT_PUBLIC_URL = os.environ.get("BOT_PUBLIC_URL", "")  # URL pública do bot no Koyeb
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
                self._json({"ativos": ativos, "expirados": inativos,
                            "tokens_livres": tokens_livres,
                            "receita": f"{ativos*14.90:.2f}"}); return

            if cmd == "clientes":
                c = db(); cur = c.cursor()
                cur.execute("""SELECT chat_id, ativo, validade, criado_em, modo, site_url, nome_canal
                    FROM clientes ORDER BY criado_em DESC""")
                rows = cur.fetchall(); cur.close(); c.close()
                result = []
                for chat_id, ativo, validade, criado, modo, site_url, nome_canal in rows:
                    dias = (validade - datetime.utcnow()).days if validade else -1
                    result.append({
                        "chat_id": chat_id,
                        "ativo": bool(ativo and dias >= 0),
                        "validade": validade.strftime("%d/%m/%Y") if validade else None,
                        "dias_rest": dias,
                        "modo": modo or "completo",
                        "site_url": site_url or "",
                        "nome_canal": nome_canal or ""
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




            if cmd.startswith("config_nome:"):
                from urllib.parse import unquote
                _, cid, nome = cmd.split(":", 2)
                nome = unquote(nome)
                c = db(); cur = c.cursor()
                cur.execute("UPDATE clientes SET nome_canal=%s WHERE chat_id=%s",
                    (None if nome=="remover" else nome, int(cid)))
                c.commit(); cur.close(); c.close()
                self._json({"ok": True}); return

            if cmd.startswith("token_add:"):
                from urllib.parse import unquote
                token_raw = unquote(cmd[len("token_add:"):]).strip().upper()
                if not token_raw:
                    self._json({"ok": False, "error": "Token vazio"}); return
                c = db(); cur = c.cursor()
                try:
                    cur.execute("INSERT INTO tokens(token,usado) VALUES(%s,FALSE)", (token_raw,))
                    c.commit(); cur.close(); c.close()
                    self._json({"ok": True, "token": token_raw}); return
                except Exception as e:
                    cur.close(); c.close()
                    self._json({"ok": False, "error": "Token já existe"}); return

            if cmd.startswith("token_del:"):
                token_raw = cmd[len("token_del:"):].strip().upper()
                c = db(); cur = c.cursor()
                cur.execute("DELETE FROM tokens WHERE token=%s AND usado=FALSE", (token_raw,))
                deleted = cur.rowcount
                c.commit(); cur.close(); c.close()
                self._json({"ok": deleted > 0, "error": "Token já usado ou não encontrado" if not deleted else ""}); return

            if cmd.startswith("cliente_del:"):
                cid = int(cmd.split(":")[1])
                c = db(); cur = c.cursor()
                cur.execute("DELETE FROM clientes WHERE chat_id=%s", (cid,))
                c.commit(); cur.close(); c.close()
                self._json({"ok": True}); return

            if cmd == "propagandas_lista":
                rows = listar_propagandas()
                result = [{"id": r[0], "texto": r[1], "ativo": bool(r[2]),
                           "criado_em": r[3].strftime("%d/%m/%Y") if r[3] else ""} for r in rows]
                self._json({"propagandas": result, "fixas": PROPAGANDAS_FIXAS}); return

            if cmd.startswith("propaganda_add:"):
                from urllib.parse import unquote
                texto = unquote(cmd[len("propaganda_add:"):])
                ok = add_propaganda(texto)
                self._json({"ok": ok}); return

            if cmd.startswith("propaganda_del:"):
                pid = int(cmd.split(":")[1])
                ok = deletar_propaganda(pid)
                self._json({"ok": ok}); return

            if cmd.startswith("propaganda_disparo:"):
                from urllib.parse import unquote
                import asyncio
                texto_raw = cmd[len("propaganda_disparo:"):]
                texto = unquote(texto_raw) if texto_raw else None
                canais = []
                if GRUPO_ID: canais.append(GRUPO_ID)
                if CANAL_VIP: canais.append(CANAL_VIP)
                txt = (texto or PROPAGANDAS_FIXAS[0]).format(contato=ADMIN_CONTATO)
                from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
                enviados = 0
                async def _send():
                    nonlocal enviados
                    bot = Bot(token=TOKEN)
                    for cid in canais:
                        try:
                            kw2 = {}
                            if cid == GRUPO_ID and TOPIC_ID:
                                kw2["message_thread_id"] = TOPIC_ID
                            await bot.send_message(
                                chat_id=cid, text=txt, parse_mode="HTML",
                                reply_markup=InlineKeyboardMarkup([[
                                    InlineKeyboardButton("💬 Falar com Admin",
                                        url=f"https://t.me/{ADMIN_CONTATO.lstrip('@')}")
                                ]]), **kw2)
                            enviados += 1
                        except: pass
                asyncio.run(_send())
                self._json({"ok": True, "enviados": enviados}); return

            if cmd == "tokens_lista":
                c = db(); cur = c.cursor()
                cur.execute("SELECT token, usado, criado_em FROM tokens ORDER BY criado_em DESC LIMIT 100")
                rows = cur.fetchall(); cur.close(); c.close()
                result = [{"token": r[0], "usado": bool(r[1]),
                           "criado_em": r[2].strftime("%d/%m/%Y %H:%M") if r[2] else ""} for r in rows]
                self._json({"tokens": result}); return

            if cmd.startswith("broadcast:"):
                from urllib.parse import unquote
                msg = unquote(cmd[len("broadcast:"):])
                c = db(); cur = c.cursor()
                cur.execute("SELECT chat_id FROM clientes WHERE ativo=TRUE AND validade > NOW()")
                chats = [r[0] for r in cur.fetchall()]; cur.close(); c.close()
                enviados = 0
                import asyncio
                async def _send_all():
                    nonlocal enviados
                    from telegram import Bot
                    bot = Bot(token=TOKEN)
                    for cid in chats:
                        try:
                            await bot.send_message(chat_id=cid, text=msg)
                            enviados += 1
                        except: pass
                asyncio.run(_send_all())
                self._json({"ok": True, "enviados": enviados}); return

            if cmd == "historico":
                c = db(); cur = c.cursor()
                cur.execute("""SELECT chat_id, token, criado_em, validade
                    FROM clientes ORDER BY criado_em DESC LIMIT 50""")
                rows = cur.fetchall(); cur.close(); c.close()
                result = [{"chat_id": r[0], "token": r[1],
                           "criado_em": r[2].strftime("%d/%m/%Y %H:%M") if r[2] else "",
                           "validade": r[3].strftime("%d/%m/%Y") if r[3] else ""} for r in rows]
                self._json({"historico": result}); return


            if cmd == "premios_lista":
                c = db(); cur = c.cursor()
                cur.execute("""SELECT id, tipo, nome, conteudo, valor, usado, data_exp, criado_em
                    FROM premios ORDER BY tipo, usado, id DESC""")
                rows = cur.fetchall(); cur.close(); c.close()
                result = [{"id":r[0],"tipo":r[1],"nome":r[2],"conteudo":r[3],
                           "valor":float(r[4]),"usado":bool(r[5]),"data_exp":r[6],
                           "criado_em":r[7].strftime("%d/%m/%Y") if r[7] else ""} for r in rows]
                # Contagem por tipo
                from collections import Counter
                disp = Counter(r["tipo"] for r in result if not r["usado"])
                self._json({"premios": result, "disponiveis": dict(disp)}); return

            if cmd.startswith("premio_add:"):
                from urllib.parse import unquote
                import json
                raw = unquote(cmd[len("premio_add:"):])
                data = json.loads(raw)
                c = db(); cur = c.cursor()
                cur.execute("INSERT INTO premios(tipo,nome,conteudo,valor,data_exp) VALUES(%s,%s,%s,%s,%s)",
                    (data["tipo"], data["nome"], data["conteudo"], float(data["valor"]), data.get("data_exp")))
                c.commit(); cur.close(); c.close()
                self._json({"ok": True}); return

            if cmd.startswith("premio_del:"):
                pid = int(cmd.split(":")[1])
                c = db(); cur = c.cursor()
                cur.execute("DELETE FROM premios WHERE id=%s AND usado=FALSE", (pid,))
                ok = cur.rowcount > 0
                c.commit(); cur.close(); c.close()
                self._json({"ok": ok}); return

            if cmd == "resgates_lista":
                c = db(); cur = c.cursor()
                cur.execute("""SELECT r.user_id, p.tipo, p.nome, r.valor, r.criado_em
                    FROM resgates r JOIN premios p ON r.premio_id=p.id
                    ORDER BY r.criado_em DESC LIMIT 50""")
                rows = cur.fetchall(); cur.close(); c.close()
                result = [{"user_id":r[0],"tipo":r[1],"nome":r[2],"valor":float(r[3]),
                           "criado_em":r[4].strftime("%d/%m/%Y %H:%M") if r[4] else ""} for r in rows]
                self._json({"resgates": result}); return

            if cmd == "creditos_lista":
                c = db(); cur = c.cursor()
                cur.execute("SELECT user_id, saldo, atualizado FROM creditos ORDER BY saldo DESC LIMIT 50")
                rows = cur.fetchall(); cur.close(); c.close()
                result = [{"user_id":r[0],"saldo":float(r[1]),
                           "atualizado":r[2].strftime("%d/%m/%Y") if r[2] else ""} for r in rows]
                self._json({"creditos": result}); return

            if cmd.startswith("credito_add_manual:"):
                parts = cmd.split(":")
                uid, val = int(parts[1]), float(parts[2])
                ok = add_saldo(uid, val)
                self._json({"ok": ok, "saldo": get_saldo(uid)}); return

            self._json({"error": "Comando desconhecido."}, 400)
        except Exception as e:
            logging.error(f"AdminAPI: {e}")
            self._json({"error": str(e)}, 500)


    def do_POST(self):
        """Webhook do Mercado Pago."""
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/webhook/mp":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                import json
                data = json.loads(body)
                if data.get("type") == "payment":
                    payment_id = str(data.get("data", {}).get("id", ""))
                    if payment_id:
                        status = verificar_pagamento_mp(payment_id)
                        if status == "approved":
                            c = db(); cur = c.cursor()
                            cur.execute("SELECT user_id, valor, status FROM pagamentos WHERE payment_id=%s", (payment_id,))
                            row = cur.fetchone()
                            if row and row[2] == "pending":
                                user_id, valor = row[0], float(row[1])
                                cur.execute("UPDATE pagamentos SET status='approved' WHERE payment_id=%s", (payment_id,))
                                c.commit()
                                add_saldo(user_id, valor)
                                cur.close(); c.close()
                                # Notifica o usuário
                                import asyncio
                                async def _notify():
                                    from telegram import Bot
                                    bot = Bot(token=TOKEN)
                                    saldo = get_saldo(user_id)
                                    await bot.send_message(
                                        chat_id=user_id,
                                        text=f"✅ <b>Pagamento confirmado!</b>\n\n"
                                             f"💰 R$ {valor:.2f} adicionado ao seu saldo\n"
                                             f"🏦 Saldo atual: <b>R$ {saldo:.2f}</b>\n\n"
                                             f"Use /credito para resgatar seus prêmios!",
                                        parse_mode="HTML"
                                    )
                                    # Avisa admin também
                                    if ADMIN_ID:
                                        await bot.send_message(
                                            chat_id=ADMIN_ID,
                                            text=f"💸 Pagamento recebido!\nUser: {user_id}\nValor: R$ {valor:.2f}",
                                        )
                                asyncio.run(_notify())
                            else:
                                if row: cur.close(); c.close()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")
                return
        except Exception as e:
            logging.error(f"Webhook MP: {e}")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

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
            cur.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS nome_canal TEXT DEFAULT NULL")
            cur.execute("ALTER TABLE tokens ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP DEFAULT NOW()")
            c.commit()
        except: pass
        # Propagandas agendadas
        cur.execute("""CREATE TABLE IF NOT EXISTS propagandas (
            id        SERIAL PRIMARY KEY,
            texto     TEXT NOT NULL,
            ativo     BOOLEAN DEFAULT TRUE,
            criado_em TIMESTAMP DEFAULT NOW()
        );""")
        # Controle de rotação de propagandas
        cur.execute("""CREATE TABLE IF NOT EXISTS propa_state (
            id        INTEGER PRIMARY KEY DEFAULT 1,
            ultimo_idx INTEGER DEFAULT 0
        );""")
        cur.execute("INSERT INTO propa_state(id,ultimo_idx) VALUES(1,0) ON CONFLICT DO NOTHING")
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

        # Sistema de créditos
        cur.execute("""CREATE TABLE IF NOT EXISTS creditos (
            user_id    BIGINT PRIMARY KEY,
            saldo      NUMERIC(10,2) DEFAULT 0,
            atualizado TIMESTAMP DEFAULT NOW()
        );""")
        # Prêmios cadastrados pelo admin
        cur.execute("""CREATE TABLE IF NOT EXISTS premios (
            id         SERIAL PRIMARY KEY,
            tipo       TEXT NOT NULL,
            nome       TEXT NOT NULL,
            conteudo   TEXT NOT NULL,
            valor      NUMERIC(10,2) NOT NULL,
            usado      BOOLEAN DEFAULT FALSE,
            data_exp   TEXT DEFAULT NULL,
            criado_em  TIMESTAMP DEFAULT NOW()
        );""")
        # Resgates realizados
        cur.execute("""CREATE TABLE IF NOT EXISTS resgates (
            id         SERIAL PRIMARY KEY,
            user_id    BIGINT NOT NULL,
            premio_id  INTEGER NOT NULL,
            valor      NUMERIC(10,2) NOT NULL,
            criado_em  TIMESTAMP DEFAULT NOW()
        );""")
        # Pagamentos PIX pendentes
        cur.execute("""CREATE TABLE IF NOT EXISTS pagamentos (
            payment_id TEXT PRIMARY KEY,
            user_id    BIGINT NOT NULL,
            valor      NUMERIC(10,2) NOT NULL,
            status     TEXT DEFAULT 'pending',
            criado_em  TIMESTAMP DEFAULT NOW()
        );""")
        c.commit(); cur.close(); c.close()
        logging.info("✅ Banco pronto (v8 SaaS)")
    except Exception as e:
        logging.error(f"Banco: {e}")


# ── Propagandas ────────────────────────────────────────────────────────────
PROPAGANDAS_FIXAS = [
    "🎬 <b>Transforme seu canal do Telegram em um cinema!</b>\n\nCom o <b>StreamFlix Bot</b> seu canal recebe automaticamente:\n🎥 Filmes em cartaz todo dia\n🔥 Séries populares\n🚀 Lançamentos antes de todo mundo\n\n💬 Fale comigo: {contato}",
    "🍿 <b>Seu canal merece mais do que posts manuais!</b>\n\nO <b>StreamFlix Bot</b> posta filmes, séries e trailers no automático — sem você fazer nada.\n\n✅ Configuração rápida\n✅ Conteúdo todo dia\n✅ Preço acessível\n\n👉 {contato}",
    "📺 <b>Dono de canal no Telegram?</b>\n\nVeja o que o <b>StreamFlix Bot</b> pode fazer pelo seu canal:\n\n🎬 Filmes em cartaz diariamente\n📅 Lançamentos futuros\n⭐ Rankings populares\n\nSeu canal nunca mais fica parado. 👉 {contato}",
    "🚀 <b>Automatize seu canal de séries e filmes!</b>\n\nNão perca mais tempo postando manualmente. O <b>StreamFlix Bot</b> faz tudo no piloto automático.\n\n💰 Plano mensal acessível\n🎯 Conteúdo certeiro para seu público\n\n📩 {contato}",
    "🎥 <b>Quer engajar mais no seu canal?</b>\n\nConteúdo de filmes e séries todo dia = audiência ativa todo dia.\n\nO <b>StreamFlix Bot</b> já está no ar em canais como este. Quer também?\n\n👇 {contato}",
]

def get_propagandas():
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT texto FROM propagandas WHERE ativo=TRUE ORDER BY id")
        rows = [r[0] for r in cur.fetchall()]; cur.close(); c.close()
        return rows
    except: return []

def get_proximo_idx():
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT ultimo_idx FROM propa_state WHERE id=1")
        r = cur.fetchone()
        idx = (r[0] + 1) if r else 0
        cur.execute("UPDATE propa_state SET ultimo_idx=%s WHERE id=1", (idx,))
        c.commit(); cur.close(); c.close()
        return idx
    except: return 0

def add_propaganda(texto):
    try:
        c = db(); cur = c.cursor()
        cur.execute("INSERT INTO propagandas(texto) VALUES(%s)", (texto,))
        c.commit(); cur.close(); c.close()
        return True
    except: return False

def listar_propagandas():
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT id, texto, ativo, criado_em FROM propagandas ORDER BY id DESC")
        rows = cur.fetchall(); cur.close(); c.close()
        return rows
    except: return []

def deletar_propaganda(pid):
    try:
        c = db(); cur = c.cursor()
        cur.execute("DELETE FROM propagandas WHERE id=%s", (pid,))
        c.commit(); cur.close(); c.close()
        return True
    except: return False


# ── Handlers de Crédito ────────────────────────────────────────────────────
async def cmd_credito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    saldo = get_saldo(user_id)
    premios = get_premios_disponiveis()

    # Tipos disponíveis
    NOMES_TIPO = {
        "xtream": "Conta Xtream IPTV",
        "vip": "Código VIP StreamFlix",
    }
    tipos = {}
    for p in premios:
        if p["tipo"] not in tipos:
            tipos[p["tipo"]] = {"qtd": 0, "valor": p["valor"]}
        tipos[p["tipo"]]["qtd"] += 1

    texto = (
        f"💰 <b>Seus Créditos StreamFlix</b>\n\n"
        f"🏦 Saldo atual: <b>R$ {saldo:.2f}</b>\n\n"
    )

    if tipos:
        texto += "🎁 <b>Prêmios disponíveis:</b>\n"
        for tipo, info in tipos.items():
            emoji = "📺" if tipo == "xtream" else "🎟️" if tipo == "vip" else "🎁"
            nome_tipo = NOMES_TIPO.get(tipo, tipo.upper())
            texto += f"{emoji} {info['qtd']}x {nome_tipo} — R$ {info['valor']:.2f} cada\n"
        texto += "\nEscolha uma opção abaixo:"
    else:
        texto += "⚠️ Nenhum prêmio disponível no momento."

    botoes = []
    # Botões de recarga
    botoes.append([
        InlineKeyboardButton("💳 Adicionar R$2,00", callback_data="pix:2.00"),
        InlineKeyboardButton("💳 Adicionar R$5,99", callback_data="pix:5.99"),
    ])
    botoes.append([
        InlineKeyboardButton("💳 Adicionar R$10,00", callback_data="pix:10.00"),
        InlineKeyboardButton("💳 Adicionar R$20,00", callback_data="pix:20.00"),
    ])
    # Botões de resgate
    for tipo, info in tipos.items():
        emoji = "📺" if tipo == "xtream" else "🎟️" if tipo == "vip" else "🎁"
        botoes.append([InlineKeyboardButton(
            f"{emoji} {NOMES_TIPO.get(tipo, tipo.upper())} — R$ {info['valor']:.2f}",  # botão resgate
            callback_data=f"resgatar:{tipo}"
        )])

    await update.message.reply_text(texto, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(botoes))

async def callback_credito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    data = q.data

    if data.startswith("pix:"):
        valor = float(data.split(":")[1])
        saldo_atual = get_saldo(user_id)
        await q.edit_message_text(
            f"⏳ Gerando PIX de R$ {valor:.2f}...",
            parse_mode="HTML"
        )
        pix, erro = criar_pix_mp(user_id, valor, f"StreamFlix Créditos R${valor:.2f}")
        if erro:
            await q.edit_message_text(
                f"❌ Erro ao gerar PIX: {erro}\n\nTente novamente mais tarde.",
                parse_mode="HTML"
            )
            return
        texto = (
            f"💳 <b>PIX gerado!</b>\n\n"
            f"💰 Valor: <b>R$ {valor:.2f}</b>\n"
            f"⏰ Válido por 30 minutos\n\n"
            f"<b>Código PIX (copia e cola):</b>\n"
            f"<code>{pix['pix_code']}</code>\n\n"
            f"✅ Após o pagamento seu saldo será atualizado automaticamente!"
        )
        botoes = [[InlineKeyboardButton("🔄 Verificar pagamento", callback_data=f"check:{pix['payment_id']}")]]
        await q.edit_message_text(texto, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(botoes))

    elif data.startswith("check:"):
        payment_id = data.split(":", 1)[1]
        status = verificar_pagamento_mp(payment_id)
        if status == "approved":
            await q.edit_message_text(
                "✅ <b>Pagamento confirmado!</b>\nSeu saldo foi atualizado. Use /credito para resgatar.",
                parse_mode="HTML"
            )
        elif status == "pending":
            await q.answer("⏳ Aguardando confirmação do pagamento...", show_alert=True)
        else:
            await q.answer(f"Status: {status or 'não encontrado'}", show_alert=True)

    elif data.startswith("resgatar:"):
        tipo = data.split(":", 1)[1]
        premios = get_premios_disponiveis(tipo)
        if not premios:
            await q.answer("⚠️ Nenhum prêmio disponível nessa categoria!", show_alert=True)
            return
        valor = premios[0]["valor"]
        saldo = get_saldo(user_id)
        if saldo < valor:
            await q.answer("💰 Saldo insuficiente!", show_alert=True)
            await q.edit_message_text(
                f"❌ <b>Saldo insuficiente!</b>\n\n"
                f"💰 Seu saldo: <b>R$ {saldo:.2f}</b>\n"
                f"💳 Necessário: <b>R$ {valor:.2f}</b>\n\n"
                f"Adicione créditos para continuar.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💳 Adicionar créditos", callback_data=f"voltar_credito")
                ]])
            )
            return
        # Confirmar resgate
        botoes = [
            [InlineKeyboardButton(f"✅ Confirmar — R$ {valor:.2f}", callback_data=f"confirmar:{tipo}")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")]
        ]
        await q.edit_message_text(
            f"🎁 <b>Confirmar resgate?</b>\n\n"
            f"Tipo: <b>{NOMES_TIPO.get(tipo, tipo.upper())}</b>\n"
            f"Valor: <b>R$ {valor:.2f}</b>\n"
            f"Saldo atual: <b>R$ {saldo:.2f}</b>\n"
            f"Saldo após: <b>R$ {saldo-valor:.2f}</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(botoes)
        )

    elif data.startswith("confirmar:"):
        tipo = data.split(":", 1)[1]
        premio = resgatar_premio(user_id, tipo)
        if not premio:
            await q.edit_message_text(
                "❌ Saldo insuficiente ou prêmio indisponível. Use /credito para ver seu saldo.",
                parse_mode="HTML"
            )
            return
        # Monta mensagem do prêmio
        if tipo == "xtream":
            linhas = premio["conteudo"].split("|")
            host = linhas[0] if len(linhas)>0 else "—"
            login = linhas[1] if len(linhas)>1 else "—"
            senha = linhas[2] if len(linhas)>2 else "—"
            exp = premio.get("data_exp") or "—"
            texto = (
                f"🎉 <b>Prêmio resgatado com sucesso!</b>\n\n"
                f"📺 <b>Conta Xtream</b>\n"
                f"🌐 Host: <code>{host}</code>\n"
                f"👤 Login: <code>{login}</code>\n"
                f"🔑 Senha: <code>{senha}</code>\n"
                f"📅 Expira: {exp}\n\n"
                f"💰 R$ {premio['valor']:.2f} descontado do saldo."
            )
        elif tipo == "vip":
            texto = (
                f"🎉 <b>Prêmio resgatado com sucesso!</b>\n\n"
                f"🎟️ <b>Código VIP App</b>\n"
                f"<code>{premio['conteudo']}</code>\n\n"
                f"💰 R$ {premio['valor']:.2f} descontado do saldo."
            )
        else:
            texto = (
                f"🎉 <b>Prêmio resgatado!</b>\n\n"
                f"🎁 {premio['nome']}\n"
                f"<code>{premio['conteudo']}</code>\n\n"
                f"💰 R$ {premio['valor']:.2f} descontado do saldo."
            )
        # Avisa admin
        if ADMIN_ID:
            try:
                from telegram import Bot
                bot_notify = Bot(token=TOKEN)
                import asyncio
                async def _notify_admin():
                    await bot_notify.send_message(
                        chat_id=ADMIN_ID,
                        text=f"🎁 Resgate realizado!\nUser: {user_id}\nTipo: {tipo}\nValor: R$ {premio['valor']:.2f}"
                    )
                asyncio.run(_notify_admin())
            except: pass
        await q.edit_message_text(texto, parse_mode="HTML")

    elif data == "cancelar":
        await q.edit_message_text("❌ Resgate cancelado.")

    elif data == "voltar_credito":
        # Redireciona para o menu de créditos
        user_id2 = q.from_user.id
        saldo2 = get_saldo(user_id2)
        premios2 = get_premios_disponiveis()
        tipos2 = {}
        for p in premios2:
            if p["tipo"] not in tipos2:
                tipos2[p["tipo"]] = {"qtd": 0, "valor": p["valor"]}
            tipos2[p["tipo"]]["qtd"] += 1
        NOMES_TIPO2 = {"xtream": "Conta Xtream IPTV", "vip": "Código VIP StreamFlix"}
        texto2 = f"💰 <b>Seus Créditos StreamFlix</b>\n\n🏦 Saldo atual: <b>R$ {saldo2:.2f}</b>\n\n"
        botoes2 = []
        botoes2.append([
            InlineKeyboardButton("💳 Adicionar R$2,00", callback_data="pix:2.00"),
            InlineKeyboardButton("💳 Adicionar R$5,99", callback_data="pix:5.99"),
        ])
        botoes2.append([
            InlineKeyboardButton("💳 Adicionar R$10,00", callback_data="pix:10.00"),
            InlineKeyboardButton("💳 Adicionar R$20,00", callback_data="pix:20.00"),
        ])
        for tipo2, info2 in tipos2.items():
            emoji2 = "📺" if tipo2 == "xtream" else "🎟️" if tipo2 == "vip" else "🎁"
            botoes2.append([InlineKeyboardButton(
                f"{emoji2} {NOMES_TIPO2.get(tipo2, tipo2.upper())} — R$ {info2['valor']:.2f}",
                callback_data=f"resgatar:{tipo2}"
            )])
        await q.edit_message_text(texto2, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(botoes2))

# ── Funções de cliente ─────────────────────────────────────────────────────

# ── Sistema de Créditos ────────────────────────────────────────────────────
def get_saldo(user_id):
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT saldo FROM creditos WHERE user_id=%s", (user_id,))
        r = cur.fetchone(); cur.close(); c.close()
        return float(r[0]) if r else 0.0
    except: return 0.0

def add_saldo(user_id, valor):
    try:
        c = db(); cur = c.cursor()
        cur.execute("""INSERT INTO creditos(user_id, saldo) VALUES(%s,%s)
            ON CONFLICT(user_id) DO UPDATE SET saldo=creditos.saldo+%s, atualizado=NOW()""",
            (user_id, valor, valor))
        c.commit(); cur.close(); c.close()
        return True
    except: return False

def sub_saldo(user_id, valor):
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT saldo FROM creditos WHERE user_id=%s", (user_id,))
        r = cur.fetchone()
        if not r or float(r[0]) < valor:
            cur.close(); c.close(); return False
        cur.execute("UPDATE creditos SET saldo=saldo-%s, atualizado=NOW() WHERE user_id=%s", (valor, user_id))
        c.commit(); cur.close(); c.close()
        return True
    except: return False

def get_premios_disponiveis(tipo=None):
    try:
        c = db(); cur = c.cursor()
        if tipo:
            cur.execute("SELECT id, tipo, nome, conteudo, valor, data_exp FROM premios WHERE usado=FALSE AND tipo=%s ORDER BY id", (tipo,))
        else:
            cur.execute("SELECT id, tipo, nome, conteudo, valor, data_exp FROM premios WHERE usado=FALSE ORDER BY tipo, id")
        rows = cur.fetchall(); cur.close(); c.close()
        return [{"id":r[0],"tipo":r[1],"nome":r[2],"conteudo":r[3],"valor":float(r[4]),"data_exp":r[5]} for r in rows]
    except: return []

def resgatar_premio(user_id, tipo):
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT id, nome, conteudo, valor, data_exp FROM premios WHERE usado=FALSE AND tipo=%s ORDER BY id LIMIT 1 FOR UPDATE", (tipo,))
        r = cur.fetchone()
        if not r:
            cur.close(); c.close(); return None
        pid, nome, conteudo, valor, data_exp = r
        # Desconta saldo
        cur.execute("SELECT saldo FROM creditos WHERE user_id=%s", (user_id,))
        sr = cur.fetchone()
        if not sr or float(sr[0]) < float(valor):
            cur.close(); c.close(); return None
        cur.execute("UPDATE creditos SET saldo=saldo-%s WHERE user_id=%s", (valor, user_id))
        cur.execute("UPDATE premios SET usado=TRUE WHERE id=%s", (pid,))
        cur.execute("INSERT INTO resgates(user_id,premio_id,valor) VALUES(%s,%s,%s)", (user_id, pid, valor))
        c.commit(); cur.close(); c.close()
        return {"nome":nome,"conteudo":conteudo,"valor":float(valor),"data_exp":data_exp}
    except Exception as e:
        logging.error(f"resgatar_premio: {e}"); return None

def criar_pix_mp(user_id, valor, descricao):
    """Cria cobrança PIX via Mercado Pago e retorna o pix_copy_paste."""
    if not MP_TOKEN:
        return None, "MP_ACCESS_TOKEN não configurado"
    try:
        import uuid
        idempotency = str(uuid.uuid4())
        payload = {
            "transaction_amount": float(valor),
            "description": descricao,
            "payment_method_id": "pix",
            "payer": {"email": f"user{user_id}@streamflix.bot"},
            "notification_url": f"{BOT_PUBLIC_URL}/webhook/mp" if BOT_PUBLIC_URL else None
        }
        if not payload["notification_url"]:
            del payload["notification_url"]
        headers = {
            "Authorization": f"Bearer {MP_TOKEN}",
            "Content-Type": "application/json",
            "X-Idempotency-Key": idempotency
        }
        r = requests.post("https://api.mercadopago.com/v1/payments", json=payload, headers=headers, timeout=15)
        data = r.json()
        if r.status_code not in (200, 201):
            return None, data.get("message","Erro MP")
        payment_id = str(data["id"])
        pix_code = data.get("point_of_interaction",{}).get("transaction_data",{}).get("qr_code","")
        # Salva no banco
        c = db(); cur = c.cursor()
        cur.execute("INSERT INTO pagamentos(payment_id,user_id,valor) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
            (payment_id, user_id, valor))
        c.commit(); cur.close(); c.close()
        return {"payment_id": payment_id, "pix_code": pix_code, "valor": valor}, None
    except Exception as e:
        return None, str(e)

def verificar_pagamento_mp(payment_id):
    """Verifica status de um pagamento no MP."""
    if not MP_TOKEN: return None
    try:
        r = requests.get(f"https://api.mercadopago.com/v1/payments/{payment_id}",
            headers={"Authorization": f"Bearer {MP_TOKEN}"}, timeout=10)
        return r.json().get("status")
    except: return None

def set_nome_canal(chat_id, nome):
    try:
        c = db(); cur = c.cursor()
        cur.execute("UPDATE clientes SET nome_canal=%s WHERE chat_id=%s", (nome, chat_id))
        c.commit(); cur.close(); c.close()
        return True
    except: return False

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



async def job_propaganda(context: ContextTypes.DEFAULT_TYPE):
    """Roda 3x ao dia: posta propaganda rotativa nos canais principais."""
    canais = []
    if GRUPO_ID: canais.append(GRUPO_ID)
    if CANAL_VIP: canais.append(CANAL_VIP)
    if not canais: return

    # Pega propagandas do banco; usa as fixas como fallback
    custom = get_propagandas()
    todas = custom if custom else PROPAGANDAS_FIXAS
    idx = get_proximo_idx() % len(todas)
    texto = todas[idx].format(contato=ADMIN_CONTATO)

    for cid in canais:
        try:
            kw = {}
            if cid == GRUPO_ID and TOPIC_ID:
                kw["message_thread_id"] = TOPIC_ID
            await context.bot.send_message(
                chat_id=cid, text=texto, parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💬 Falar com Admin", url=f"https://t.me/{ADMIN_CONTATO.lstrip('@')}")
                ]]), **kw
            )
        except Exception as e: logging.error(f"Propaganda {cid}: {e}")

async def enviar_propaganda_agora(context, texto_custom=None):
    """Disparo manual de propaganda pelo painel."""
    canais = []
    if GRUPO_ID: canais.append(GRUPO_ID)
    if CANAL_VIP: canais.append(CANAL_VIP)
    if not canais: return 0
    texto = (texto_custom or PROPAGANDAS_FIXAS[0]).format(contato=ADMIN_CONTATO)
    enviados = 0
    for cid in canais:
        try:
            await context.bot.send_message(
                chat_id=cid, text=texto, parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💬 Falar com Admin", url=f"https://t.me/{ADMIN_CONTATO.lstrip('@')}")
                ]])
            )
            enviados += 1
        except Exception as e: logging.error(f"Propaganda manual {cid}: {e}")
    return enviados

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
    if CANAL_VIP and CANAL_VIP not in chats: chats.append(CANAL_VIP)

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

    # Créditos
    app.add_handler(CommandHandler("credito", cmd_credito))
    app.add_handler(CallbackQueryHandler(callback_credito, pattern="^(pix:|check:|resgatar:|confirmar:|cancelar|voltar_credito)"))
    # Texto e callbacks
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Jobs automáticos
    jq = app.job_queue
    if jq:
        jq.run_daily(job_diario_manha,           time=datetime.strptime("11:00","%H:%M").time())  # 8h BRT
        jq.run_daily(job_diario_noite,           time=datetime.strptime("23:00","%H:%M").time())  # 20h BRT
        jq.run_repeating(job_verificar_vencimentos, interval=3600, first=60)                       # a cada 1h
        jq.run_daily(job_propaganda, time=datetime.strptime("13:00","%H:%M").time())  # 10h BRT
        jq.run_daily(job_propaganda, time=datetime.strptime("18:00","%H:%M").time())  # 15h BRT
        jq.run_daily(job_propaganda, time=datetime.strptime("22:00","%H:%M").time())  # 19h BRT

    logging.info(f"✅ Bot v8.0 SaaS Online — {SITE_URL}")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    while True:
        try: main()
        except Exception as e:
            logging.error(f"💥 Reiniciando: {e}"); time.sleep(10)
