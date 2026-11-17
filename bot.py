# ================= BOT DE CINEMA v8.3 — StreamFlix SaaS Edition =================
# Novidades v8.3:
#   ✅ Cards de filme/série com layout limpo, categoria, sinopse e hashtags
#   ✅ Agenda temática (lançamentos de manhã, sugestão da noite por dia da semana)
#   ✅ Promo do app e propaganda das 15h no mesmo visual do grupo
# =================================================================================

import os, html, time, random, logging, threading, secrets, string, unicodedata
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, quote
import requests, psycopg2
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    BotCommand, BotCommandScopeDefault, BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats, BotCommandScopeChat,
    InlineQueryResultArticle, InlineQueryResultPhoto, InputTextMessageContent,
)
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          filters, ContextTypes, CallbackQueryHandler,
                          ChatMemberHandler, InlineQueryHandler)

# ── Variáveis de ambiente ──────────────────────────────────────────────────
TOKEN         = os.environ.get("TOKEN",        os.environ.get("BOT_TOKEN", ""))
TMDB_KEY      = os.environ.get("TMDB_API_KEY", "")
DATABASE_URL  = os.environ.get("DATABASE_URL", "")
SITE_URL      = os.environ.get("SITE_URL",     "https://www.streamflixvip.online")
APP_URL       = os.environ.get("APP_URL",      "https://www.streamflixvip.online/downloads/app-latest.apk")
ADMIN_ID      = int(os.environ.get("ADMIN_ID", "0"))   # Seu user_id do Telegram (não chat_id do canal)
GRUPO_ID      = int(os.environ.get("GRUPO_ID", "0"))   # Seu canal principal (streamflixofc)
CANAL_VIP     = int(os.environ.get("CANAL_VIP", "0"))    # Canal VIP (streamflixvip)
ADMIN_CONTATO = os.environ.get("ADMIN_CONTATO", "@RaffDimitri")  # Contato para propagandas
TOPIC_ID      = int(os.environ.get("TOPIC_ID", "0"))
CANAL_SUPORTE = "https://t.me/streamflixofc"
MP_TOKEN      = os.environ.get("MP_ACCESS_TOKEN", "")  # Mercado Pago Access Token
BOT_PUBLIC_URL = os.environ.get("BOT_PUBLIC_URL", "")  # URL pública do bot no Koyeb
DIAS_SEM_REPETIR = 30  # recarregado abaixo com env, depois de env_int()
DIAS_PLANO       = 30

def env_bool(name, default=True):
    v = os.environ.get(name)
    if v is None or str(v).strip() == "":
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on", "sim")

def env_int(name, default):
    try:
        return int(str(os.environ.get(name, default)).strip())
    except (TypeError, ValueError):
        return default

# Painel: origens extras (vírgula). Sempre libera o painel oficial e localhost.
PANEL_CORS_ORIGINS = os.environ.get("PANEL_CORS_ORIGINS", "")

# Engajamento (todos ligados por padrão; desligue com 0/false/off)
WELCOME_ENABLED         = env_bool("WELCOME_ENABLED", True)
WELCOME_DELETE_SECONDS  = env_int("WELCOME_DELETE_SECONDS", 180)  # 0 = não apaga
WELCOME_RATE_SECONDS    = env_int("WELCOME_RATE_SECONDS", 45)
WELCOME_INCLUDE_CLIENTS = env_bool("WELCOME_INCLUDE_CLIENTS", False)
BUTTON_ASSISTA          = env_bool("BUTTON_ASSISTA", True)
APP_PROMO_ENABLED       = env_bool("APP_PROMO_ENABLED", True)
APP_PROMO_HOUR_UTC      = env_int("APP_PROMO_HOUR_UTC", 20)   # 17h America/Fortaleza
POLL_ENABLED            = env_bool("POLL_ENABLED", True)
POLL_WEEKDAY            = env_int("POLL_WEEKDAY", 4)          # 0=seg ... 4=sexta
POLL_HOUR_UTC           = env_int("POLL_HOUR_UTC", 21)        # 18h America/Fortaleza
DOWNLOADER_CELULAR      = os.environ.get("DOWNLOADER_CELULAR", "6085325")
DOWNLOADER_TV           = os.environ.get("DOWNLOADER_TV", "3422972")

# Engajamento v8.2 (todos opcionais; padrões pensados para não lotar o grupo)
PUBLIC_SEARCH             = env_bool("PUBLIC_SEARCH", True)            # busca no privado sem ser cliente SaaS
SEND_TRAILER_MESSAGE      = env_bool("SEND_TRAILER_MESSAGE", False)    # 2ª mensagem de trailer (já há botão no card)
APP_PROMO_INCLUDE_CLIENTS = env_bool("APP_PROMO_INCLUDE_CLIENTS", False)
POLL_INCLUDE_CLIENTS      = env_bool("POLL_INCLUDE_CLIENTS", False)
COMMAND_RATE_SECONDS      = env_int("COMMAND_RATE_SECONDS", 8)
GROUP_SEARCH_RATE_SECONDS = env_int("GROUP_SEARCH_RATE_SECONDS", 30)
# Horários UTC da propaganda, separados por vírgula. Antes: 13,18,22 (10h/15h/19h Fortaleza).
# Padrão novo: uma vez às 18:00 UTC (15h America/Fortaleza). Para voltar: PROPAGANDA_HOURS_UTC=13,18,22
PROPAGANDA_HOURS_UTC      = os.environ.get("PROPAGANDA_HOURS_UTC", "18")
SET_BOT_PROFILE           = env_bool("SET_BOT_PROFILE", False)         # só altera descrição se ligar (e o usuário aprovar o texto)
INLINE_MODE               = env_bool("INLINE_MODE", True)

# Visual e agenda v8.3
THEMED_NIGHTS             = env_bool("THEMED_NIGHTS", True)            # tema da noite por dia da semana
MANHA_HOUR_UTC            = env_int("MANHA_HOUR_UTC", 11)             # 8h America/Fortaleza
NOITE_HOUR_UTC            = env_int("NOITE_HOUR_UTC", 23)             # 20h America/Fortaleza
MANHA_INCLUIR_SERIE       = env_bool("MANHA_INCLUIR_SERIE", True)      # 1 filme + 1 série de manhã (senão 2 filmes)
PROPAGANDA_USE_DB         = env_bool("PROPAGANDA_USE_DB", False)       # 1 = usa textos de propaganda salvos no painel
DIAS_SEM_REPETIR          = env_int("DIAS_SEM_REPETIR", 30)
TMDB_POSTER_SIZE          = (os.environ.get("TMDB_POSTER_SIZE", "w780") or "w780").strip()
MANHA_HEADER              = os.environ.get("MANHA_HEADER", "🌅 Bom dia! Lançamentos de hoje 👇")
NOITE_HEADER              = os.environ.get("NOITE_HEADER", "🌙 Boa noite! Sugestão da noite 👇")

# IA opcional (desligada por padrão). Endpoint compatível com OpenAI /chat/completions.
# Recomendado: Groq (AI_BASE_URL e AI_MODEL já vêm no padrão; basta a chave).
AI_ENABLED                = env_bool("AI_ENABLED", False)
AI_BASE_URL               = (os.environ.get("AI_BASE_URL") or "https://api.groq.com/openai/v1").strip().rstrip("/")
AI_API_KEY                = os.environ.get("AI_API_KEY", "")
AI_MODEL                  = (os.environ.get("AI_MODEL") or "openai/gpt-oss-20b").strip()
AI_RATE_SECONDS           = env_int("AI_RATE_SECONDS", 20)
AI_DAILY_CAP              = env_int("AI_DAILY_CAP", 15)   # por usuário, por dia (America/Fortaleza)
AI_MAX_TOKENS             = env_int("AI_MAX_TOKENS", 350)

IMG_BASE  = f"https://image.tmdb.org/t/p/{TMDB_POSTER_SIZE}"
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
# Não logar URLs da API do Telegram (contêm o token)
for _n in ("httpx", "httpcore", "telegram.request"):
    logging.getLogger(_n).setLevel(logging.WARNING)

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
        origin = (self.headers.get("Origin") or "").strip()
        if cors_origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Pass")
        self.send_header("Access-Control-Max-Age", "86400")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors(); self.end_headers()

    def _json(self, data, status=200):
        body = __import__('json').dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors(); self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except ValueError:
            return None
        if length <= 0 or length > 1_000_000:
            return None
        raw = self.rfile.read(length)
        try:
            import json
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _admin_pw_and_cmd(self, parsed, body_json=None):
        """Senha: header X-Admin-Pass, depois JSON, depois query (legado, transição)."""
        from urllib.parse import parse_qs
        params = parse_qs(parsed.query)
        cmd = params.get("cmd", [""])[0]
        pw = self.headers.get("X-Admin-Pass") or ""
        if body_json:
            if not pw:
                pw = str(body_json.get("pass") or body_json.get("password") or "")
            cmd = str(body_json.get("cmd") or cmd or "")
        if not pw:
            pw = params.get("pass", [""])[0]
        return pw, cmd

    def _handle_admin(self, parsed, body_json=None):
        pw, cmd = self._admin_pw_and_cmd(parsed, body_json)

        if not PANEL_PASS or not pw or not secrets.compare_digest(str(pw), str(PANEL_PASS)):
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
                # Mesma proteção usada em token_del/premio_del: não deixa
                # apagar de forma "muda" um cliente que ainda está ativo e
                # com validade em dia — evita clique duplo/acidental apagar
                # um cliente pagante sem querer.
                cur.execute("SELECT ativo, validade FROM clientes WHERE chat_id=%s", (cid,))
                row = cur.fetchone()
                if not row:
                    cur.close(); c.close()
                    self._json({"ok": False, "error": "Cliente não encontrado"}); return
                ativo, validade = row
                ainda_vigente = bool(ativo) and validade is not None and validade > datetime.utcnow()
                if ainda_vigente and "force=1" not in cmd:
                    cur.close(); c.close()
                    self._json({"ok": False, "error": "Cliente ainda ativo/vigente. Revogue antes ou confirme exclusão forçada."}); return
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
                cur.execute("""SELECT id, tipo, nome, conteudo, valor, usado, data_exp, criado_em, emoji
                    FROM premios ORDER BY tipo, usado, id DESC""")
                rows = cur.fetchall(); cur.close(); c.close()
                result = [{"id":r[0],"tipo":r[1],"nome":r[2],"conteudo":r[3],
                           "valor":float(r[4]),"usado":bool(r[5]),"data_exp":r[6],
                           "criado_em":r[7].strftime("%d/%m/%Y") if r[7] else "","emoji":r[8]} for r in rows]
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
                cur.execute("INSERT INTO premios(tipo,nome,conteudo,valor,data_exp,emoji) VALUES(%s,%s,%s,%s,%s,%s)",
                    (data["tipo"], data["nome"], data["conteudo"], float(data["valor"]), data.get("data_exp"), data.get("emoji")))
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
        """API do painel (POST /admin) e webhook do Mercado Pago."""
        parsed = urlparse(self.path)
        if parsed.path == "/admin":
            body_json = self._read_json_body()
            self._handle_admin(parsed, body_json)
            return
        try:
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
    porta = int(os.environ.get("PORT", "8000"))
    # Durante rolling deploy do Koyeb, a instância antiga pode ainda estar
    # de saída e segurando a porta por alguns segundos — tenta algumas
    # vezes com espera curta em vez de morrer direto com OSError.
    for tentativa in range(10):
        try:
            HTTPServer(("0.0.0.0", porta), AdminHandler).serve_forever()
            return
        except OSError as e:
            logging.warning(f"start_health: porta {porta} ocupada ({e}), tentando de novo em 3s...")
            time.sleep(3)
    logging.error("start_health: não conseguiu abrir a porta após várias tentativas.")


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
            # Emoji próprio por prêmio — usado pelos tipos "streaming" (Netflix,
            # Paramount, etc.) e "personalizado", que não têm emoji fixo como
            # xtream (📺) e vip (🎟️) têm.
            cur.execute("ALTER TABLE premios ADD COLUMN IF NOT EXISTS emoji TEXT DEFAULT NULL")
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
# Textos antigos de aluguel do bot ficam só como fallback se PROPAGANDA_USE_DB=1
# e o painel não tiver nenhum texto. O grupo oficial usa textos_propaganda_app().
PROPAGANDAS_FIXAS = [
    "🎬 <b>Transforme seu canal do Telegram em um cinema!</b>\n\nCom o <b>StreamFlix Bot</b> seu canal recebe automaticamente:\n🎥 Filmes em cartaz todo dia\n🔥 Séries populares\n🚀 Lançamentos antes de todo mundo\n\n💬 Fale comigo: {contato}",
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
def _montar_texto_e_botoes_credito(saldo, premios):
    """Monta o texto e os botões do menu de créditos, agrupando por
    categoria (VIP StreamFlix / Xtream Premium / Streamings) em vez de uma
    lista corrida — mais fácil de escanear no celular."""
    # Agrupa por (tipo, valor) — evita misturar planos diferentes (ex: 3 VIPs
    # com preços distintos) sob a mesma chave "tipo". Guarda também o "nome"
    # e "emoji" cadastrados no painel.
    tipos = {}
    for p in premios:
        chave = (p["tipo"], p["valor"])
        if chave not in tipos:
            tipos[chave] = {"qtd": 0, "valor": p["valor"], "tipo": p["tipo"],
                             "nome": p["nome"], "emoji": p.get("emoji")}
        tipos[chave]["qtd"] += 1

    texto = (
        f"💰 <b>Seus Créditos StreamFlix</b>\n\n"
        f"🏦 Saldo: <b>R$ {saldo:.2f}</b>\n"
    )

    SEP = "━━━━━━━━━━━━━━"
    vip_items    = [(k, v) for k, v in tipos.items() if k[0] == "vip"]
    xtream_items = [(k, v) for k, v in tipos.items() if k[0] == "xtream"]
    outros_items = [(k, v) for k, v in tipos.items() if k[0] not in ("vip", "xtream")]

    if vip_items:
        texto += f"\n{SEP}\n🎟️ VIP STREAMFLIX\n{SEP}\n"
        for (tipo, valor), info in vip_items:
            # Nome já vem como "StreamFlixVip App — 30 dias"; mostra só a
            # parte depois do "—" (o plano), já que a seção deixa claro o resto.
            plano = info["nome"].split("—")[-1].strip() if "—" in info["nome"] else info["nome"]
            texto += f"• {plano} — R$ {info['valor']:.2f} ({info['qtd']} disponíveis)\n"

    if xtream_items:
        texto += f"\n{SEP}\n📺 XTREAM PREMIUM\n{SEP}\n"
        for (tipo, valor), info in xtream_items:
            texto += f"• R$ {info['valor']:.2f} ({info['qtd']} disponíveis)\n"

    if outros_items:
        texto += f"\n{SEP}\n🎬 STREAMINGS\n{SEP}\n"
        for (tipo, valor), info in outros_items:
            texto += f"• {info['nome']} — R$ {info['valor']:.2f} ({info['qtd']} disponíveis)\n"

    if not tipos:
        texto += "\n⚠️ Nenhum prêmio disponível no momento."
    else:
        texto += "\nEscolha uma opção abaixo:"

    botoes = []
    botoes.append([InlineKeyboardButton("💳 Depositar valor personalizado", callback_data="pix_custom")])
    # Atalhos de recarga calculados a partir dos preços reais dos prêmios
    # cadastrados (não mais valores fixos) — assim eles sempre "fecham
    # redondo" com o que o cliente pode querer resgatar.
    valores_premios = sorted({info["valor"] for info in tipos.values()})
    atalhos = valores_premios[:4] if valores_premios else [10.00, 20.00]
    linha = []
    for v in atalhos:
        linha.append(InlineKeyboardButton(f"💳 R$ {v:.2f}", callback_data=f"pix:{v:.2f}"))
        if len(linha) == 2:
            botoes.append(linha); linha = []
    if linha: botoes.append(linha)

    # Botões de resgate — rótulo enxuto (emoji + nome curto + preço) já que
    # a descrição completa aparece no texto acima, evita corte no botão.
    for (tipo, valor), info in vip_items + xtream_items + outros_items:
        emoji = info["emoji"] or ("🎟️" if tipo == "vip" else "📺" if tipo == "xtream" else "✨")
        if tipo == "vip":
            rotulo = info["nome"].split("—")[-1].strip() if "—" in info["nome"] else info["nome"]
        elif tipo == "xtream":
            rotulo = "Xtream"
        else:
            rotulo = info["nome"]
        botoes.append([InlineKeyboardButton(
            f"{emoji} {rotulo} — R$ {info['valor']:.2f}",
            callback_data=f"resgatar:{tipo}:{valor:.2f}"
        )])
    return texto, botoes

async def cmd_credito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    saldo = get_saldo(user_id)
    premios = get_premios_disponiveis()
    texto, botoes = _montar_texto_e_botoes_credito(saldo, premios)
    await update.message.reply_text(texto, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(botoes))

async def _gerar_e_enviar_pix(context, chat_id, user_id, valor, q=None):
    """Gera o PIX e envia/edita a mensagem com o código. Reutilizada pelos
    botões de valor fixo e pelo fluxo de valor digitado livremente."""
    texto_gerando = f"⏳ Gerando PIX de R$ {valor:.2f}..."
    if q:
        await q.edit_message_text(texto_gerando, parse_mode="HTML")
    else:
        await context.bot.send_message(chat_id, texto_gerando, parse_mode="HTML")

    pix, erro = criar_pix_mp(user_id, valor, f"StreamFlix Créditos R${valor:.2f}")
    if erro:
        msg_erro = f"❌ Erro ao gerar PIX: {erro}\n\nTente novamente mais tarde."
        if q: await q.edit_message_text(msg_erro, parse_mode="HTML")
        else: await context.bot.send_message(chat_id, msg_erro, parse_mode="HTML")
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
    if q:
        await q.edit_message_text(texto, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(botoes))
    else:
        await context.bot.send_message(chat_id, texto, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(botoes))

async def callback_credito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    data = q.data

    if data == "pix_custom":
        context.user_data["aguardando_valor_pix"] = True
        await q.edit_message_text(
            "💳 <b>Depósito personalizado</b>\n\n"
            "Digite o valor que deseja depositar (ex: <code>47</code> ou <code>47,50</code>).\n"
            "Valor mínimo: R$ 2,00.",
            parse_mode="HTML"
        )
        return

    if data.startswith("pix:"):
        valor = float(data.split(":")[1])
        await _gerar_e_enviar_pix(context, q.message.chat_id, user_id, valor, q=q)

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
        partes = data.split(":")
        tipo = partes[1]
        valor_filtro = float(partes[2]) if len(partes) > 2 else None
        premios = get_premios_disponiveis(tipo)
        if valor_filtro is not None:
            premios = [p for p in premios if abs(p["valor"] - valor_filtro) < 0.001]
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
            [InlineKeyboardButton(f"✅ Confirmar — R$ {valor:.2f}", callback_data=f"confirmar:{tipo}:{valor:.2f}")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")]
        ]
        await q.edit_message_text(
            f"🎁 <b>Confirmar resgate?</b>\n\n"
            f"Item: <b>{premios[0]['nome']}</b>\n"
            f"Valor: <b>R$ {valor:.2f}</b>\n"
            f"Saldo atual: <b>R$ {saldo:.2f}</b>\n"
            f"Saldo após: <b>R$ {saldo-valor:.2f}</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(botoes)
        )

    elif data.startswith("confirmar:"):
        partes = data.split(":")
        tipo = partes[1]
        valor_filtro = float(partes[2]) if len(partes) > 2 else None
        premio = resgatar_premio(user_id, tipo, valor_filtro)
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
                await bot_notify.send_message(
                    chat_id=ADMIN_ID,
                    text=f"🎁 Resgate realizado!\nUser: {user_id}\nTipo: {tipo}\nValor: R$ {premio['valor']:.2f}"
                )
            except Exception as e:
                logging.error(f"Falha ao notificar admin sobre resgate: {e}")
        await q.edit_message_text(texto, parse_mode="HTML")

    elif data == "cancelar":
        await q.edit_message_text("❌ Resgate cancelado.")

    elif data == "voltar_credito":
        # Redireciona para o menu de créditos — mesma lógica de cmd_credito
        user_id2 = q.from_user.id
        saldo2 = get_saldo(user_id2)
        premios2 = get_premios_disponiveis()
        texto2, botoes2 = _montar_texto_e_botoes_credito(saldo2, premios2)
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
            cur.execute("SELECT id, tipo, nome, conteudo, valor, data_exp, emoji FROM premios WHERE usado=FALSE AND tipo=%s ORDER BY id", (tipo,))
        else:
            cur.execute("SELECT id, tipo, nome, conteudo, valor, data_exp, emoji FROM premios WHERE usado=FALSE ORDER BY tipo, id")
        rows = cur.fetchall(); cur.close(); c.close()
        return [{"id":r[0],"tipo":r[1],"nome":r[2],"conteudo":r[3],"valor":float(r[4]),"data_exp":r[5],"emoji":r[6]} for r in rows]
    except: return []

def resgatar_premio(user_id, tipo, valor_filtro=None):
    try:
        c = db(); cur = c.cursor()
        if valor_filtro is not None:
            # Filtra também por valor para não misturar planos com preços
            # diferentes dentro do mesmo "tipo" (ex: VIP 19,90 / 49,90 / 99,90)
            cur.execute(
                "SELECT id, nome, conteudo, valor, data_exp FROM premios "
                "WHERE usado=FALSE AND tipo=%s AND ABS(valor-%s)<0.001 ORDER BY id LIMIT 1 FOR UPDATE",
                (tipo, valor_filtro)
            )
        else:
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
    if chat_oficial(chat_id): return True  # grupo/canal do dono sempre liberado
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


def clientes_para_avisar():
    """Clientes ativos cuja validade vence em até 3 dias e ainda não foram avisados."""
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

def trailer_from_videos(videos, titulo):
    res = (videos or {}).get("results") or []
    t = next((x for x in res if x.get("type")=="Trailer" and x.get("site")=="YouTube"), None)
    if t: return f"https://youtu.be/{t['key']}"
    yt = next((x for x in res if x.get("site")=="YouTube"), None)
    if yt: return f"https://youtu.be/{yt['key']}"
    return f"https://www.youtube.com/results?search_query={quote((titulo or '')+' Trailer Oficial')}"

def get_trailer_url(item_id, titulo, is_tv=False, details=None):
    if details and details.get("videos"):
        return trailer_from_videos(details.get("videos"), titulo)
    v = tmdb(f"{'tv' if is_tv else 'movie'}/{item_id}/videos")
    return trailer_from_videos(v, titulo)

def ensure_https(url):
    """Telegram exige URL absoluta com https:// nos botoes inline."""
    u = (url or "").strip()
    if not u:
        return "https://www.streamflixvip.online"
    if not u.startswith(("http://", "https://")):
        u = "https://" + u.lstrip("/")
    return u.rstrip("/")

def link_app_download():
    return ensure_https(APP_URL or "https://www.streamflixvip.online/downloads/app-latest.apk")

def link_streamflix(item_id, is_tv=False, site=None):
    """Link principal (Assistir).
    Site oficial StreamFlixVIP: landing (sem player web).
    Cliente SaaS com site proprio: /?id=&type= se tiver player.
    """
    base = ensure_https(site or SITE_URL)
    if "streamflixvip.online" in base:
        return base  # landing de divulgacao
    tipo = "tv" if is_tv else "movie"
    return f"{base}/?id={item_id}&type={tipo}"

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

def cortar_sinopse(texto, limite=300):
    texto = " ".join((texto or "").split())
    if not texto:
        return "Sinopse não disponível."
    if len(texto) <= limite:
        return texto
    trecho = texto[:limite]
    cortes = [trecho.rfind(p) for p in (". ", "! ", "? ", "… ")]
    corte = max(cortes)
    if corte >= int(limite * 0.55):
        return trecho[:corte + 1].strip()
    sp = trecho.rfind(" ")
    if sp > 40:
        return trecho[:sp].rstrip(" ,;:") + "…"
    return trecho.rstrip() + "…"

def hashtag_ascii(texto):
    partes = []
    for w in (texto or "").replace("-", " ").replace("/", " ").replace("&", " ").split():
        nfkd = unicodedata.normalize("NFKD", w)
        sem = "".join(c for c in nfkd if not unicodedata.combining(c))
        limpo = "".join(c for c in sem if c.isalnum())
        if limpo:
            partes.append(limpo[:1].upper() + limpo[1:])
    return "".join(partes)

def hashtags_do_item(is_tv, gen_list):
    tags = ["#Serie" if is_tv else "#Filme"]
    vistos = {"Serie", "Filme"}
    for g in gen_list[:3]:
        for parte in (g or "").split("&"):
            slug = hashtag_ascii(parte)
            if slug and slug not in vistos:
                tags.append("#" + slug)
                vistos.add(slug)
    tags.append("#StreamFlix")
    return " ".join(tags)

def categoria_padrao(is_tv, categoria=None):
    if categoria:
        return categoria
    return "📺 SÉRIE" if is_tv else "🎬 FILME"

def url_imagem(details, item=None):
    src = details or {}
    alt = item or {}
    post = src.get("poster_path") or alt.get("poster_path")
    if post:
        return f"{IMG_BASE}{post}"
    back = src.get("backdrop_path") or alt.get("backdrop_path")
    if back:
        return f"{IMG_BASE}{back}"
    return None

CAPTION_MAX = 1024

def build_caption(details, is_tv=False, categoria=None):
    """Card limpo para o grupo: categoria, título, meta, sinopse e hashtags."""
    if not details:
        return "ℹ️ Informações indisponíveis."
    titulo     = details.get("name") if is_tv else details.get("title", "?")
    orig_title = details.get("original_name" if is_tv else "original_title", "") or ""
    ano        = (details.get("first_air_date", "") if is_tv else details.get("release_date", ""))[:4] or "?"
    rating     = details.get("vote_average") or 0
    sinopse    = cortar_sinopse(details.get("overview") or "", 300)
    gen_list   = [g.get("name") for g in details.get("genres", []) if g.get("name")]
    generos    = " • ".join(gen_list[:3])

    if is_tv:
        seasons  = details.get("number_of_seasons") or 0
        episodes = details.get("number_of_episodes") or 0
        if seasons and episodes:
            duracao = f"📺 {seasons} temp., {episodes} eps."
        elif seasons:
            duracao = f"📺 {seasons} temp."
        elif episodes:
            duracao = f"📺 {episodes} eps."
        else:
            duracao = ""
    else:
        runtime = details.get("runtime") or 0
        duracao = f"⏱ {formatar_runtime(runtime)}" if runtime else ""

    meta_partes = []
    if rating:
        meta_partes.append(f"⭐ {rating:.1f}")
    if duracao:
        meta_partes.append(duracao)
    if generos:
        meta_partes.append("🎭 " + generos)
    meta_linha = " • ".join(meta_partes)

    tag = categoria_padrao(is_tv, categoria)
    linhas = [html.escape(tag), ""]
    titulo_l = f"<b>{html.escape(titulo or '?')}</b>"
    if ano and ano != "?":
        titulo_l += f" ({html.escape(ano)})"
    linhas.append(titulo_l)
    if orig_title and orig_title != titulo:
        linhas.append(f"<i>{html.escape(orig_title)}</i>")
    if meta_linha:
        linhas.append("")
        linhas.append(html.escape(meta_linha))
    linhas += ["", html.escape(sinopse), "", hashtags_do_item(is_tv, gen_list)]

    texto = "\n".join(linhas)
    if len(texto) <= CAPTION_MAX:
        return texto
    # Encolhe a sinopse até caber no limite do Telegram
    reserva = len(texto) - len(html.escape(sinopse))
    novo_limite = max(80, CAPTION_MAX - reserva - 8)
    sinopse = cortar_sinopse(details.get("overview") or "", novo_limite)
    linhas[-3] = html.escape(sinopse)
    texto = "\n".join(linhas)
    return texto[:CAPTION_MAX]

# ── Itens enviados por cliente ─────────────────────────────────────────────
_enviados_mem = {}  # (chat_id, item_id) -> datetime

def ids_enviados(chat_id, dias=None):
    """IDs já postados neste chat na janela (tabela sent_items + memória)."""
    janela = DIAS_SEM_REPETIR if dias is None else dias
    corte = datetime.utcnow() - timedelta(days=janela)
    ids = set()
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT item_id FROM sent_items WHERE chat_id=%s AND sent_at>%s",
                    (chat_id, corte))
        ids = {r[0] for r in cur.fetchall()}
        cur.close(); c.close()
    except Exception:
        pass
    for (cid, iid), ts in list(_enviados_mem.items()):
        if cid == chat_id and ts >= corte:
            ids.add(iid)
    return ids

def ja_enviados(chat_id, tipo):
    # Mantém a assinatura antiga; a deduplicação dos jobs ignora o tipo.
    return ids_enviados(chat_id)

def marcar_enviado(chat_id, item_id, tipo):
    if chat_id and item_id:
        _enviados_mem[(chat_id, item_id)] = datetime.utcnow()
    try:
        c = db(); cur = c.cursor()
        cur.execute("""INSERT INTO sent_items VALUES(%s,%s,%s,%s)
            ON CONFLICT(chat_id,item_id,item_type) DO UPDATE SET sent_at=EXCLUDED.sent_at""",
            (chat_id, item_id, tipo, datetime.utcnow()))
        c.commit(); cur.close(); c.close()
    except Exception as e:
        logging.error(e)

def filtrar(chat_id, itens, tipo, permitir_repetir=True):
    env   = ids_enviados(chat_id)
    novos = [i for i in itens if i.get("id") not in env]
    if novos:
        return novos
    return list(itens) if permitir_repetir else []

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

def item_is_tv(item, default=False):
    if not item:
        return default
    media = item.get("media_type")
    if media == "tv":
        return True
    if media == "movie":
        return False
    if item.get("name") and not item.get("title"):
        return True
    return default

def markup_card(assist_url, baixar_url, trailer_url=None, modo="completo"):
    label_assist = "▶️ Assista no StreamFlix" if BUTTON_ASSISTA else (
        "🎬 VER NO SITE / APP" if modo == "simples" else "🌐 VER NO SITE / APP"
    )
    row1 = [InlineKeyboardButton(label_assist, url=assist_url)]
    if trailer_url:
        row1.append(InlineKeyboardButton("🎞 Trailer", url=trailer_url))
    return InlineKeyboardMarkup([
        row1,
        [InlineKeyboardButton("📲 Baixar app", url=baixar_url)],
    ])

async def send_item(context, chat_id, item, is_tv=False, tipo="movie", categoria=None):
    if not item: return
    iid     = item.get("id")
    details = tmdb_details(iid, is_tv=is_tv) or item
    title   = details.get("name") if is_tv else details.get("title","?")
    caption = build_caption(details, is_tv=is_tv, categoria=categoria)
    modo     = get_modo(chat_id)
    site     = get_site_url(chat_id)
    url_trl = get_trailer_url(iid, title, is_tv=is_tv, details=details)
    tem_trailer = "youtu.be/" in url_trl or "youtube.com/watch" in url_trl

    assist_url = link_streamflix(iid, is_tv=is_tv, site=site)
    baixar_url = link_app_download() if "streamflixvip.online" in ensure_https(site) else ensure_https(site)
    keyboard = markup_card(assist_url, baixar_url, url_trl if tem_trailer else None, modo=modo)
    foto = url_imagem(details, item)
    try:
        if foto: await enviar(context, chat_id, photo=foto, caption=caption, markup=keyboard)
        else:    await enviar(context, chat_id, text=caption, markup=keyboard)
        if tem_trailer and SEND_TRAILER_MESSAGE:
            trl_kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("▶️ Ver Trailer no YouTube", url=url_trl)
            ]])
            await enviar(context, chat_id,
                         text="\U0001f3ac <b>Confira o Trailer:</b>\n" + url_trl,
                         markup=trl_kb)
        marcar_enviado(chat_id, iid, "tv" if is_tv else tipo or "movie")
    except Exception as e: logging.error(e)

async def enviar_lista(context, chat_id, itens, is_tv=False, tipo="movie", limite=3, categoria=None, permitir_repetir=True):
    """Mantido para fluxos que ainda enviam cards seguidos (jobs usam send_item direto)."""
    itens = filtrar(chat_id, itens, tipo, permitir_repetir=permitir_repetir)
    if permitir_repetir:
        random.shuffle(itens)
    for item in itens[:limite]:
        await send_item(context, chat_id, item, is_tv=is_tv or item_is_tv(item), tipo=tipo,
                        categoria=categoria)

# ── Verificação de acesso ──────────────────────────────────────────────────
def chat_oficial(chat_id):
    """Grupo/canal principal do StreamFlix (não só o GRUPO_ID)."""
    return bool(chat_id) and chat_id in {i for i in (GRUPO_ID, CANAL_VIP) if i}

def acesso_conteudo(chat_id):
    return chat_oficial(chat_id) or cliente_ativo(chat_id)

def is_privado(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat) and chat.type == "private"

def is_grupo(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat) and chat.type in ("group", "supergroup")

def parse_horas_utc(valor, padrao):
    horas = []
    for part in str(valor or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            h = int(part)
        except ValueError:
            continue
        if 0 <= h <= 23 and h not in horas:
            horas.append(h)
    return horas or list(padrao)

_rate_bucket = {}  # (user_id, bucket) -> timestamp

def rate_ok(user_id, bucket, seconds):
    if not seconds or seconds <= 0 or not user_id:
        return True
    now = time.time()
    if len(_rate_bucket) > 4000:
        cutoff = now - 600
        stale = [k for k, ts in _rate_bucket.items() if ts < cutoff]
        for k in stale:
            _rate_bucket.pop(k, None)
    key = (user_id, bucket)
    last = _rate_bucket.get(key, 0)
    if now - last < seconds:
        return False
    _rate_bucket[key] = now
    return True

async def avisar_aguarde(update: Update, seconds=None):
    msg = update.effective_message
    if not msg:
        return
    texto = "⏳ Aguarde uns segundos antes de buscar de novo."
    try:
        await msg.reply_text(texto)
    except Exception:
        pass

async def verificar_acesso(update: Update, context, *, silent=False) -> bool:
    chat = update.effective_chat
    if not chat:
        return False
    cid = chat.id
    if acesso_conteudo(cid):
        return True
    if chat.type == "private" and PUBLIC_SEARCH:
        return True
    if silent or chat.type in ("group", "supergroup", "channel"):
        return False
    if update.message:
        await update.message.reply_text(
            "🔒 <b>Acesso bloqueado!</b>\n\n"
            "Seu plano não está ativo ou expirou.\n\n"
            f"Para ativar ou renovar:\n{CANAL_SUPORTE}",
            parse_mode="HTML"
        )
    return False

# ── Comandos de cliente ────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    chat = update.effective_chat
    cid  = chat.id
    user = update.effective_user
    payload = (context.args[0].strip() if context.args else "")
    nome = (user.first_name if user else None) or "aí"

    # Nos grupos, não despeja teclado nem o texto longo de SaaS.
    if chat.type in ("group", "supergroup"):
        bot_info = await context.bot.get_me()
        uname = bot_info.username or ""
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Abrir no privado", url=f"https://t.me/{uname}?start=1")],
            [InlineKeyboardButton("📲 Baixar app", url=link_app_download())],
        ])
        # Tira o teclado de resposta no grupo (ele atrapalha o papo).
        try:
            await update.message.reply_text(
                "👋 Eu sou o bot do <b>StreamFlix VIP</b>.\n"
                "O teclado fixo foi retirado daqui para o papo ficar mais limpo.\n"
                "Fale comigo no privado, ou use /filme, /serie, /top10 e /comandos.",
                parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
        except Exception:
            pass
        await update.message.reply_text("✨ Acesse:", reply_markup=kb)
        return

    if payload.lower() in ("saas", "canal", "bot"):
        bot_info = await context.bot.get_me()
        saas_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Suporte", url=CANAL_SUPORTE)],
            [InlineKeyboardButton("⬅️ Voltar", callback_data="start:home")],
        ])
        await update.message.reply_text(
            texto_saas(bot_info.username), parse_mode="HTML", reply_markup=saas_kb)
        return

    await update.message.reply_text(
        texto_start_app(nome, payload),
        parse_mode="HTML",
        reply_markup=menu_teclado())
    await update.message.reply_text(
        "✨ Escolha uma opção:",
        reply_markup=markup_start_privado())

    if payload.lower() in ("indique", "indicar", "ganhe"):
        await update.message.reply_text(texto_indique(), parse_mode="HTML",
                                        reply_markup=markup_cta_app())
    elif payload.lower() in ("baixar", "app", "download"):
        await update.message.reply_text(
            "📱 Toque abaixo para baixar o app:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📱 Baixar app", url=link_app_download())],
                [InlineKeyboardButton("🌐 Site", url=ensure_https(SITE_URL))],
            ]))
    elif payload.lower() in ("lancamentos", "lançamentos", "cartaz"):
        d = tmdb("movie/now_playing", {"region": "BR"})
        if d and d.get("results"):
            await enviar_lista(context, cid, d.get("results", []), tipo="now_playing")
        else:
            await enviar(context, cid, text="😕 Não encontrei lançamentos agora. Tente de novo em instantes.")

async def cmd_indique(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if is_grupo(update):
        bot_info = await context.bot.get_me()
        uname = bot_info.username or ""
        await update.message.reply_text(
            "🎁 <b>Indique e ganhe +7 dias VIP</b>\n\n"
            + texto_indique() +
            "\n\nPara o menu completo, abra o bot no privado.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Abrir no privado", url=f"https://t.me/{uname}?start=indique")],
                [InlineKeyboardButton("📱 Baixar app", url=link_app_download())],
            ]))
        return
    await update.message.reply_text(
        "🎁 <b>Indique e ganhe +7 dias VIP</b>\n\n" + texto_indique(),
        parse_mode="HTML", reply_markup=markup_cta_app())


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
        await update.message.reply_text(
            "ℹ️ Este comando é para quem usa o bot no próprio canal.\n\n"
            "Para o app StreamFlix, use /indique (ganhe +7 dias VIP) ou /credito.\n"
            f"Suporte: {CANAL_SUPORTE}")
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
    try:
        qtd = min(int(context.args[0]) if context.args else 1, 10)
        if qtd < 1:
            qtd = 1
    except (TypeError, ValueError):
        await update.message.reply_text("⚠️ Use: <code>/gerar [quantidade]</code>", parse_mode="HTML")
        return
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
    """Posta propaganda rotativa nos canais principais (horários: PROPAGANDA_HOURS_UTC)."""
    canais = []
    if GRUPO_ID: canais.append(GRUPO_ID)
    if CANAL_VIP: canais.append(CANAL_VIP)
    if not canais: return

    custom = get_propagandas() if PROPAGANDA_USE_DB else []
    if custom:
        todas = custom
        idx = get_proximo_idx() % len(todas)
        texto = aplicar_contato(todas[idx])
        markup = markup_cta_app()
    else:
        todas = textos_propaganda_app()
        idx = get_proximo_idx() % len(todas)
        texto = todas[idx]
        markup = markup_cta_app()

    for cid in canais:
        try:
            kw = {}
            if cid == GRUPO_ID and TOPIC_ID:
                kw["message_thread_id"] = TOPIC_ID
            await context.bot.send_message(
                chat_id=cid, text=texto, parse_mode="HTML",
                reply_markup=markup, **kw
            )
        except Exception as e: logging.error(f"Propaganda {cid}: {e}")

async def enviar_propaganda_agora(context, texto_custom=None):
    """Disparo manual de propaganda pelo painel."""
    canais = []
    if GRUPO_ID: canais.append(GRUPO_ID)
    if CANAL_VIP: canais.append(CANAL_VIP)
    if not canais: return 0
    if texto_custom:
        texto = aplicar_contato(texto_custom)
    else:
        texto = textos_propaganda_app()[0]
    enviados = 0
    for cid in canais:
        try:
            await context.bot.send_message(
                chat_id=cid, text=texto, parse_mode="HTML",
                reply_markup=markup_cta_app()
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
    """Posta conteúdo para TODOS os clientes ativos, com tema e cards novos."""
    chats = chats_destinatarios()
    for cid in chats:
        try:
            if turno == "manha":
                await postar_manha(context, cid)
            else:
                await postar_noite(context, cid)
        except Exception as e:
            logging.error(f"Job {turno} → {cid}: {e}")

def weekday_fortaleza():
    return (datetime.utcnow() - timedelta(hours=3)).weekday()

TEMAS_NOITE = {
    0: {"header": "🌙 Segunda do riso! Comédia para começar a semana 👇",
        "genres": "35", "kind": "movie", "cat": "🍿 SUGESTÃO DA NOITE"},
    1: {"header": "🌙 Terça de ação 👇",
        "genres": "28", "kind": "movie", "cat": "🍿 SUGESTÃO DA NOITE"},
    2: {"header": "🌙 Quarta do susto! Terror 👇",
        "genres": "27", "kind": "movie", "cat": "🍿 SUGESTÃO DA NOITE"},
    3: {"header": "🌙 Quinta de drama e romance 👇",
        "genres": "10749|18", "kind": "movie", "cat": "🍿 SUGESTÃO DA NOITE"},
    4: {"header": "🌙 Sexta em família 👇",
        "genres": "16|10751", "kind": "movie", "cat": "🍿 SUGESTÃO DA NOITE"},
    5: {"header": "🌙 Sábado de séries 👇",
        "genres": "", "kind": "tv", "cat": "📺 SÉRIE"},
    6: {"header": "🌙 Domingo clássico 👇",
        "genres": "", "kind": "movie", "cat": "🍿 SUGESTÃO DA NOITE", "classicos": True},
}

def _pick_novos(chat_id, itens, is_tv, qtd=2):
    tipo = "tv" if is_tv else "movie"
    novos = filtrar(chat_id, list(itens or []), tipo, permitir_repetir=False)
    if not novos:
        return []
    # varia entre os primeiros, sem repetir gênero no mesmo envio quando der
    random.shuffle(novos)
    escolhidos, generos_usados = [], set()
    for item in novos:
        gens = set()
        for g in item.get("genre_ids") or []:
            gens.add(g)
        for g in item.get("genres") or []:
            if isinstance(g, dict) and g.get("id"):
                gens.add(g["id"])
        if gens and generos_usados and gens <= generos_usados and len(novos) > qtd:
            continue
        escolhidos.append(item)
        generos_usados |= gens
        if len(escolhidos) >= qtd:
            break
    if len(escolhidos) < qtd:
        for item in novos:
            if item not in escolhidos:
                escolhidos.append(item)
            if len(escolhidos) >= qtd:
                break
    return escolhidos

async def postar_manha(context, cid):
    header = MANHA_HEADER or "🌅 Bom dia! Lançamentos de hoje 👇"
    await enviar(context, cid, text=f"<b>{html.escape(header)}</b>")
    filmes = ((tmdb("movie/now_playing", {"region": "BR"}) or {}).get("results") or [])
    escolhidos = []
    if MANHA_INCLUIR_SERIE:
        series = ((tmdb("tv/on_the_air") or {}).get("results") or [])
        fm = _pick_novos(cid, filmes, False, 1)
        sr = _pick_novos(cid, series, True, 1)
        if fm:
            escolhidos.append((fm[0], False, "🎬 LANÇAMENTO"))
        if sr:
            escolhidos.append((sr[0], True, "📺 SÉRIE"))
    if len(escolhidos) < 2:
        extra = _pick_novos(cid, filmes, False, 2)
        for item in extra:
            if all(item.get("id") != e[0].get("id") for e in escolhidos):
                escolhidos.append((item, False, "🎬 LANÇAMENTO"))
            if len(escolhidos) >= 2:
                break
    if not escolhidos:
        logging.info(f"Manhã: nada novo para {cid}")
        return
    for item, is_tv, cat in escolhidos[:2]:
        await send_item(context, cid, item, is_tv=is_tv, tipo="tv" if is_tv else "movie", categoria=cat)

async def postar_noite(context, cid):
    tema = TEMAS_NOITE.get(weekday_fortaleza(), TEMAS_NOITE[0]) if THEMED_NIGHTS else None
    header = (tema["header"] if tema else None) or NOITE_HEADER or "🌙 Boa noite! Sugestão da noite 👇"
    await enviar(context, cid, text=f"<b>{html.escape(header)}</b>")
    if tema and THEMED_NIGHTS:
        is_tv = tema["kind"] == "tv"
        params = {"sort_by": "popularity.desc", "vote_count.gte": 200, "page": random.randint(1, 3)}
        if tema.get("classicos"):
            params = {
                "primary_release_date.gte": "1950-01-01",
                "primary_release_date.lte": "1999-12-31",
                "sort_by": "vote_average.desc",
                "vote_count.gte": 500,
                "page": random.randint(1, 3),
            }
        elif tema.get("genres"):
            params["with_genres"] = tema["genres"]
        endpoint = "discover/tv" if is_tv else "discover/movie"
        itens = ((tmdb(endpoint, params) or {}).get("results") or [])
        escolhidos = _pick_novos(cid, itens, is_tv, 2)
        cat = tema["cat"]
        for item in escolhidos:
            await send_item(context, cid, item, is_tv=is_tv, tipo="tv" if is_tv else "movie", categoria=cat)
        if escolhidos:
            return
    # Fallback: populares / top, gêneros variados
    d = tmdb("movie/popular", {"region": "BR", "page": random.randint(1, 3)}) or {}
    escolhidos = _pick_novos(cid, d.get("results") or [], False, 2)
    if len(escolhidos) < 2:
        d2 = tmdb("movie/top_rated", {"page": random.randint(1, 5)}) or {}
        for item in _pick_novos(cid, d2.get("results") or [], False, 2):
            if all(item.get("id") != e.get("id") for e in escolhidos):
                escolhidos.append(item)
            if len(escolhidos) >= 2:
                break
    for item in escolhidos[:2]:
        await send_item(context, cid, item, is_tv=False, tipo="movie", categoria="🍿 SUGESTÃO DA NOITE")

async def job_diario_manha(context): await job_diario_todos(context, "manha")
async def job_diario_noite(context): await job_diario_todos(context, "noite")

def chats_destinatarios():
    """Clientes ativos + grupo principal e canal VIP, sem duplicar."""
    try:
        c = db(); cur = c.cursor()
        cur.execute("SELECT chat_id FROM clientes WHERE ativo=TRUE AND validade > NOW()")
        chats = [r[0] for r in cur.fetchall()]; cur.close(); c.close()
    except Exception:
        chats = []
    if GRUPO_ID and GRUPO_ID not in chats:
        chats.append(GRUPO_ID)
    if CANAL_VIP and CANAL_VIP not in chats:
        chats.append(CANAL_VIP)
    return chats

def label_botao_assistir():
    return "▶️ Assista no StreamFlix" if BUTTON_ASSISTA else "🌐 VER NO SITE / APP"

def markup_cta_app():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label_botao_assistir(), url=ensure_https(SITE_URL))],
        [InlineKeyboardButton("📲 Baixar app", url=link_app_download())],
    ])

def texto_indique():
    return (
        "📲 Downloader — Indique e ganhe: +7 dias VIP\n"
        f"📱 Celular: <code>{html.escape(str(DOWNLOADER_CELULAR))}</code>\n"
        f"📺 TV: <code>{html.escape(str(DOWNLOADER_TV))}</code>"
    )

def aplicar_contato(texto):
    try:
        return (texto or "").format(contato=ADMIN_CONTATO, site=ensure_https(SITE_URL))
    except (KeyError, IndexError, ValueError):
        return texto or ""

def textos_propaganda_app():
    site = html.escape(ensure_https(SITE_URL))
    ind = texto_indique()
    return [
        (
            "🍿 <b>StreamFlix VIP</b> — filmes e séries no app\n\n"
            f"🌐 {site}\n\n"
            f"{ind}"
        ),
        (
            "📲 <b>Leve o cinema na palma da mão</b>\n\n"
            "Filmes, séries e TV no StreamFlix.\n"
            f"🌐 {site}\n\n"
            f"{ind}"
        ),
        (
            "🎁 <b>Indique e ganhe +7 dias VIP</b>\n\n"
            "Chame um amigo para o StreamFlix e aproveite o bônus no app.\n"
            f"🌐 {site}\n\n"
            f"{ind}"
        ),
    ]

def texto_promo_app():
    site = html.escape(ensure_https(SITE_URL))
    return (
        "📲 <b>Assista no app StreamFlix</b>\n\n"
        "Filmes, séries e TV no celular e na TV.\n"
        f"🌐 {site}\n\n"
        f"{texto_indique()}"
    )

MENU_BOTOES = {
    "🎥 Em Cartaz", "🚀 Em Breve", "🌟 Populares", "📺 Séries",
    "🔥 Em Alta", "🎲 Sugestão", "🎭 Por Gênero", "🎞️ Por Época",
    "🔍 Buscar", "❓ Ajuda",
}

def menu_teclado():
    return ReplyKeyboardMarkup([
        ["🎥 Em Cartaz", "🚀 Em Breve"],
        ["🌟 Populares", "📺 Séries"],
        ["🔥 Em Alta", "🎲 Sugestão"],
        ["🎭 Por Gênero", "🎞️ Por Época"],
        ["🔍 Buscar", "❓ Ajuda"],
    ], resize_keyboard=True)

def markup_start_privado():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Baixar app", url=link_app_download()),
         InlineKeyboardButton("🌐 Site", url=ensure_https(SITE_URL))],
        [InlineKeyboardButton("🎬 Ver lançamentos", callback_data="start:lancamentos"),
         InlineKeyboardButton("🎁 Indique e ganhe", callback_data="start:indique")],
        [InlineKeyboardButton("💬 Suporte", url=CANAL_SUPORTE)],
    ])

def texto_start_app(first_name, payload=""):
    nome = html.escape(first_name or "aí")
    extra = ""
    if payload.startswith("ref_"):
        extra = "\nObrigado por vir pelo convite! Use os códigos abaixo no Downloader.\n\n"
    return (
        f"👋 Olá, <b>{nome}</b>! Bem-vindo ao <b>StreamFlix</b>.\n\n"
        f"{extra}"
        "Filmes, séries e TV no celular e na TV.\n"
        f"🌐 {html.escape(ensure_https(SITE_URL))}\n\n"
        f"{texto_indique()}\n\n"
        "Toque nos botões abaixo ou busque com /filme e /serie."
    )

def texto_saas(bot_username):
    return (
        "📋 <b>QUERO O BOT NO MEU CANAL</b>\n\n"
        "<b>1️⃣ Adquira seu plano:</b>\n"
        f"👉 {CANAL_SUPORTE}\n\n"
        "<b>2️⃣ Adicione o bot ao seu canal:</b>\n"
        "• Abra seu canal no Telegram\n"
        "• Toque nos 3 pontos (⋮) no canto superior\n"
        "• Vá em <b>Administradores</b>\n"
        "• Toque em <b>Adicionar Administrador</b>\n"
        f"• Pesquise: <code>@{html.escape(bot_username or '')}</code>\n"
        "• Ative a permissão <b>Enviar Mensagens</b> ✅\n"
        "• Confirme\n\n"
        "<b>3️⃣ Ative seu plano no canal:</b>\n"
        "Digite no seu canal:\n"
        "<code>/ativar SEU_TOKEN</code>\n\n"
        f"❓ Dúvidas? {CANAL_SUPORTE}"
    )

def teclado_em_linhas(botoes, por_linha=2):
    rows, linha = [], []
    for b in botoes:
        linha.append(b)
        if len(linha) == por_linha:
            rows.append(linha); linha = []
    if linha:
        rows.append(linha)
    return InlineKeyboardMarkup(rows)

# ── Boas-vindas a novos membros ────────────────────────────────────────────
_welcome_last = {}  # chat_id -> timestamp, anti-flood

def cors_origin_allowed(origin):
    if not origin:
        return False
    allowed = {
        "https://cinema-bot-painel.vercel.app",
    }
    for extra in (PANEL_CORS_ORIGINS or "").split(","):
        extra = extra.strip()
        if extra:
            allowed.add(extra.rstrip("/"))
    if origin in allowed:
        return True
    try:
        u = urlparse(origin)
    except Exception:
        return False
    if u.scheme not in ("http", "https"):
        return False
    host = (u.hostname or "").lower()
    return host in ("localhost", "127.0.0.1")

def chats_boas_vindas():
    chats = set()
    if GRUPO_ID:
        chats.add(GRUPO_ID)
    if CANAL_VIP:
        chats.add(CANAL_VIP)
    for part in os.environ.get("WELCOME_CHAT_IDS", "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            chats.add(int(part))
        except ValueError:
            logging.warning(f"WELCOME_CHAT_IDS inválido: {part}")
    if WELCOME_INCLUDE_CLIENTS:
        for cid in chats_destinatarios():
            chats.add(cid)
    return chats

async def _apagar_mensagem(context):
    data = context.job.data or {}
    try:
        await context.bot.delete_message(data["chat_id"], data["message_id"])
    except Exception:
        pass

async def enviar_boas_vindas(context, chat_id, users):
    if not WELCOME_ENABLED or not users:
        return
    if chat_id not in chats_boas_vindas():
        return
    now = time.time()
    last = _welcome_last.get(chat_id, 0)
    if WELCOME_RATE_SECONDS > 0 and (now - last) < WELCOME_RATE_SECONDS:
        logging.info(f"Boas-vindas: rate-limit no chat {chat_id}, pulando.")
        return
    _welcome_last[chat_id] = now
    nomes = []
    for u in users:
        if getattr(u, "is_bot", False):
            continue
        nomes.append(html.escape(u.first_name or "aí"))
    if not nomes:
        return
    quem = ", ".join(nomes[:5])
    if len(nomes) > 5:
        quem += f" e mais {len(nomes) - 5}"
    texto = (
        f"👋 Bem-vindo(a), {quem}!\n\n"
        "🎬 Filmes, séries e TV no StreamFlix\n"
        f"🌐 {html.escape(ensure_https(SITE_URL))}\n\n"
        f"{texto_indique()}"
    )
    msg = await enviar(context, chat_id, text=texto, markup=markup_cta_app())
    if msg and WELCOME_DELETE_SECONDS > 0 and context.job_queue:
        context.job_queue.run_once(
            _apagar_mensagem,
            when=WELCOME_DELETE_SECONDS,
            data={"chat_id": chat_id, "message_id": msg.message_id},
            name=f"wdel-{chat_id}-{msg.message_id}",
        )

async def on_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.new_chat_members:
        return
    await enviar_boas_vindas(context, update.effective_chat.id, msg.new_chat_members)

async def on_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmu = update.chat_member
    if not cmu:
        return
    old, new = cmu.old_chat_member, cmu.new_chat_member
    if not new or not new.user:
        return
    was_out = old.status in ("left", "kicked") if old else True
    is_in = new.status in ("member", "administrator", "restricted", "creator")
    if was_out and is_in:
        await enviar_boas_vindas(context, update.effective_chat.id, [new.user])

# ── Post diário do app e enquete semanal ───────────────────────────────────
async def job_app_promo(context: ContextTypes.DEFAULT_TYPE):
    if not APP_PROMO_ENABLED:
        return
    texto = texto_promo_app()
    destinos = chats_destinatarios() if APP_PROMO_INCLUDE_CLIENTS else [c for c in (GRUPO_ID, CANAL_VIP) if c]
    for cid in destinos:
        try:
            await enviar(context, cid, text=texto, markup=markup_cta_app())
        except Exception as e:
            logging.error(f"App promo {cid}: {e}")

async def job_enquete_semanal(context: ContextTypes.DEFAULT_TYPE):
    if not POLL_ENABLED:
        return
    d = tmdb("trending/all/week") or {}
    itens = list(d.get("results") or [])
    filmes = [i for i in itens if i.get("media_type") in ("movie", None) and i.get("title")]
    if len(filmes) < 2:
        filmes = [i for i in itens if (i.get("title") or i.get("name"))]
    random.shuffle(filmes)
    opcoes = []
    for item in filmes:
        title = (item.get("title") or item.get("name") or "").strip()
        year = (item.get("release_date") or item.get("first_air_date") or "")[:4]
        label = f"{title} ({year})" if year else title
        if len(label) > 100:
            label = label[:97] + "…"
        if label and label not in opcoes:
            opcoes.append(label)
        if len(opcoes) >= 4:
            break
    if len(opcoes) < 2:
        logging.warning("Enquete: poucos títulos no TMDB, pulando.")
        return
    question = os.environ.get("POLL_QUESTION") or "🎬 Qual filme você quer ver no fim de semana?"
    cta = (
        "🗳️ Vote e assista no StreamFlix!\n"
        f"🌐 {html.escape(ensure_https(SITE_URL))}\n"
        f"{texto_indique()}"
    )
    destinos = chats_destinatarios() if POLL_INCLUDE_CLIENTS else [c for c in (GRUPO_ID, CANAL_VIP) if c]
    for cid in destinos:
        try:
            kw = {}
            topic = get_topic_id(cid)
            if topic:
                kw["message_thread_id"] = topic
            await context.bot.send_poll(
                chat_id=cid, question=question, options=opcoes,
                is_anonymous=True, **kw
            )
            await enviar(context, cid, text=cta, markup=markup_cta_app())
        except Exception as e:
            logging.error(f"Enquete {cid}: {e}")

# ── Handlers de texto ──────────────────────────────────────────────────────
# ── Vitrine (card + títulos com paginação) e dicas ─────────────────────────
_vitrines = {}
_bot_username = ""
_ai_daily = {}

DICAS = [
    "💡 Dica: busque um título com /filme Nome ou /serie Nome",
    "💡 Dica: no privado, use os botões do menu. O guia está em /comandos",
    "💡 Dica: indique um amigo e ganhe +7 dias VIP — toque em /indique",
    "💡 Dica: baixe o app em streamflixvip.online (Downloader no /indique)",
    "💡 Dica: veja os mais vistos da semana com /top10",
]

def dica_ocasional():
    if random.random() < 0.28:
        return random.choice(DICAS)
    return None

async def enviar_dica(context, cid):
    dica = dica_ocasional()
    if dica:
        await enviar(context, cid, text=dica)

def _vitrine_limpar():
    corte = time.time() - 3600
    for k in [k for k, v in _vitrines.items() if v.get("ts", 0) < corte]:
        _vitrines.pop(k, None)
    if len(_vitrines) > 80:
        antigos = sorted(_vitrines.items(), key=lambda kv: kv[1].get("ts", 0))
        for k, _ in antigos[: len(_vitrines) - 80]:
            _vitrines.pop(k, None)

def _vitrine_guardar(itens, is_tv, categoria, titulo):
    _vitrine_limpar()
    lid = secrets.token_hex(3)
    _vitrines[lid] = {
        "itens": list(itens)[:40],
        "is_tv": is_tv,
        "categoria": categoria,
        "titulo": titulo,
        "ts": time.time(),
    }
    return lid

def rotulo_item(item, is_tv_default=False):
    tv = item_is_tv(item, is_tv_default)
    title = (item.get("name") if tv else item.get("title")) or "?"
    year = ((item.get("first_air_date") if tv else item.get("release_date")) or "")[:4]
    nota = item.get("vote_average") or 0
    icone = "📺" if tv else "🎬"
    label = f"{icone} {title}"
    if year:
        label += f" ({year})"
    if nota:
        label += f" ⭐{nota:.1f}"
    if len(label) > 64:
        label = label[:61] + "…"
    return label

async def enviar_vitrine(context, chat_id, itens, is_tv=False, categoria=None,
                         titulo="🎬 Títulos", page=0, lista_id=None, destacar=True):
    if not lista_id:
        itens = [i for i in (itens or []) if i.get("id")]
        if not itens:
            await avisar_tmdb_vazio(context, chat_id)
            return
        tipo = "tv" if is_tv else "movie"
        novos = filtrar(chat_id, itens, tipo, permitir_repetir=False)
        itens = novos or itens
        lista_id = _vitrine_guardar(itens, is_tv, categoria, titulo)
    data = _vitrines.get(lista_id)
    if not data:
        await enviar(context, chat_id, text="⏳ Essa seleção expirou. Toque de novo no menu.")
        return
    itens = data["itens"]
    is_tv = data["is_tv"]
    categoria = data.get("categoria")
    titulo = data.get("titulo") or titulo

    if page == 0 and destacar and itens:
        feat = itens[0]
        tv = item_is_tv(feat, is_tv)
        await send_item(context, chat_id, feat, is_tv=tv, tipo="tv" if tv else "movie",
                        categoria=categoria or categoria_padrao(tv))
        inicio, fim = 1, 6
    else:
        inicio = 1 + page * 5 if destacar else page * 5
        fim = inicio + 5

    fatia = itens[inicio:fim]
    botoes = []
    for item in fatia:
        tv = item_is_tv(item, is_tv)
        kind = "tv" if tv else "movie"
        botoes.append([InlineKeyboardButton(
            rotulo_item(item, is_tv),
            callback_data=f"ver:{kind}:{item['id']}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Anterior", callback_data=f"pg:{lista_id}:{page-1}"))
    if fim < len(itens):
        nav.append(InlineKeyboardButton("Mais ▶️", callback_data=f"pg:{lista_id}:{page+1}"))
    if nav:
        botoes.append(nav)
    if botoes:
        await enviar(
            context, chat_id,
            text=f"<b>{html.escape(titulo)}</b>\nToque em um título para abrir o card.",
            markup=InlineKeyboardMarkup(botoes),
        )
    elif page > 0:
        await enviar(context, chat_id, text="Não há mais títulos por agora.")
    if page == 0:
        await enviar_dica(context, chat_id)

# ── Assistente (IA, opcional) ──────────────────────────────────────────────
def ai_system_prompt():
    site = ensure_https(SITE_URL)
    return (
        "Você é o assistente do StreamFlix VIP, um app de filmes e séries. "
        "Responda sempre em português do Brasil, de forma curta e amigável (no máximo 8 linhas). "
        "Ajude a recomendar filmes e séries, a usar o bot (/filme, /serie, /top10, /indique) e a instalar o app.\n\n"
        "O app NÃO está na Play Store, Samsung ou LG. Ele é instalado pelo site ou pelo app Downloader. Como instalar:\n"
        f"- Celular Android: abra {site}/downloads/app-latest.apk no navegador e instale o APK (permita 'instalar apps desconhecidos'), "
        f"ou no app Downloader digite o código {DOWNLOADER_CELULAR}.\n"
        f"- TV Android / TV Box / Fire TV Stick: instale o app 'Downloader' (pela loja da TV ou da Amazon), abra e digite o código {DOWNLOADER_TV}; "
        "ele baixa e instala o StreamFlix. No Fire Stick, ative 'Apps de fontes desconhecidas' para o Downloader.\n"
        f"- Site com tudo: {site}\n"
        "- O app tem Área Free; o VIP é pago por Pix dentro do app (pagamento único, sem renovação automática).\n"
        "- Indique e ganhe: no Perfil do app há um código; quando um amigo faz a primeira compra VIP com ele, você ganha +7 dias VIP.\n\n"
        "Preços do app:\n"
        "- 1 mês: R$ 9,90\n"
        "- 3 meses: R$ 24,90\n"
        "- 6 meses: R$ 49,90\n"
        "- Anual: R$ 89,90\n"
        "- Ingresso 24h: R$ 2,50\n\n"
        "Não invente preços, códigos, lojas, passos de instalação, login ou promoções que não estejam acima. "
        "Não ajude com pirataria, cracks, contas compartilhadas ilegais, ofensas ou qualquer pedido ilegal ou perigoso. "
        "Recuse com educação e redirecione para o app oficial. "
        "Se não souber, diga que não sabe e sugira o site ou /indique."
    )

def _hoje_fortaleza():
    return (datetime.utcnow() - timedelta(hours=3)).strftime("%Y%m%d")

def ai_quota_ok(uid):
    if not AI_DAILY_CAP or not uid:
        return True
    usados = _ai_daily.get((uid, _hoje_fortaleza()), 0)
    return usados < AI_DAILY_CAP

def ai_quota_inc(uid):
    if not uid:
        return
    chave = (uid, _hoje_fortaleza())
    _ai_daily[chave] = _ai_daily.get(chave, 0) + 1
    if len(_ai_daily) > 4000:
        hoje = _hoje_fortaleza()
        for k in [k for k in _ai_daily if k[1] != hoje]:
            _ai_daily.pop(k, None)

def ai_perguntar(pergunta):
    if not AI_ENABLED or not AI_API_KEY:
        return None
    url = AI_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": "Bearer " + AI_API_KEY,
        "Content-Type": "application/json",
    }
    body = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": ai_system_prompt()},
            {"role": "user", "content": (pergunta or "")[:800]},
        ],
        "max_tokens": AI_MAX_TOKENS,
        "temperature": 0.6,
    }
    try:
        r = requests.post(url, json=body, headers=headers, timeout=35)
        if r.status_code != 200:
            logging.warning(f"IA HTTP {r.status_code}")
            return None
        data = r.json()
        return ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()
    except Exception as e:
        logging.warning(f"IA falhou: {type(e).__name__}")
        return None

def mensagem_para_o_bot(update):
    """True se a pessoa mencionou o bot ou respondeu uma mensagem dele."""
    msg = update.effective_message
    if not msg:
        return False, ""
    texto = (msg.text or msg.caption or "").strip()
    reply = msg.reply_to_message
    if reply and reply.from_user and getattr(reply.from_user, "is_bot", False):
        ru = (reply.from_user.username or "")
        if not _bot_username or ru.lower() == _bot_username.lower():
            return True, texto
    if _bot_username and texto:
        mencao = "@" + _bot_username
        if mencao.lower() in texto.lower():
            import re
            q = re.sub(r"@" + re.escape(_bot_username), "", texto, flags=re.I).strip()
            return True, q
    return False, texto

async def _entregar_ia(update, context, pergunta):
    user = update.effective_user
    uid = user.id if user else 0
    chat = update.effective_chat
    cid = chat.id if chat else 0
    msg = update.effective_message
    if not AI_ENABLED or not AI_API_KEY:
        if msg:
            await msg.reply_text("🤖 O assistente ainda não está ligado. Use /filme, /serie ou /comandos.")
        return
    if not pergunta:
        if msg:
            await msg.reply_text(
                "🤖 Me pergunte algo, ou use /ia sua pergunta.\n"
                "Exemplo: <code>/ia um filme de comédia para hoje</code>",
                parse_mode="HTML")
        return
    if not rate_ok(uid, "ia", AI_RATE_SECONDS):
        if msg:
            await msg.reply_text("⏳ Aguarde uns segundos antes de perguntar de novo.")
        return
    if not ai_quota_ok(uid):
        if msg:
            await msg.reply_text("🤖 Você chegou ao limite de perguntas de hoje. Use /filme, /serie ou volte amanhã.")
        return
    try:
        await context.bot.send_chat_action(cid, "typing")
    except Exception:
        pass
    resposta = ai_perguntar(pergunta)
    ai_quota_inc(uid)
    if not resposta:
        if msg:
            await msg.reply_text("😕 Não consegui responder agora. Tente de novo em instantes, ou use /filme e /serie.")
        return
    if len(resposta) > 3500:
        resposta = resposta[:3490] + "…"
    if msg:
        await msg.reply_text(resposta)

async def avisar_tmdb_vazio(context, cid):
    await enviar(context, cid, text="😕 Não encontrei títulos agora. Tente de novo em instantes.")

async def executar_menu(context, cid, text):
    if text == "🎥 Em Cartaz":
        d = tmdb("movie/now_playing", {"region":"BR"})
        await enviar_vitrine(context, cid, (d or {}).get("results") or [],
                             categoria="🎬 LANÇAMENTO", titulo="🎬 Em cartaz agora")

    elif text == "🚀 Em Breve":
        d = tmdb("movie/upcoming", {"region":"BR"})
        await enviar_vitrine(context, cid, (d or {}).get("results") or [],
                             categoria="🎬 LANÇAMENTO", titulo="🚀 Em breve")

    elif text == "🌟 Populares":
        d = tmdb("movie/popular", {"region":"BR","page":random.randint(1,5)})
        await enviar_vitrine(context, cid, (d or {}).get("results") or [],
                             categoria="🎬 FILME", titulo="🌟 Populares")

    elif text == "📺 Séries":
        d = tmdb("tv/popular", {"page":random.randint(1,5)})
        await enviar_vitrine(context, cid, (d or {}).get("results") or [], is_tv=True,
                             categoria="📺 SÉRIE", titulo="📺 Séries em alta")

    elif text == "🔥 Em Alta":
        d = tmdb("trending/all/week")
        await enviar_vitrine(context, cid, (d or {}).get("results") or [],
                             titulo="🔥 Em alta nesta semana")

    elif text == "🎭 Por Gênero":
        btns = [InlineKeyboardButton(n, callback_data=f"gen_{i}") for n,i in GENEROS.items()]
        await enviar(context, cid, text="✨ <b>Escolha um gênero:</b>", markup=teclado_em_linhas(btns, 2))

    elif text == "🎞️ Por Época":
        btns = [InlineKeyboardButton(n, callback_data=f"era_{n}") for n in EPOCAS]
        await enviar(context, cid, text="⏳ <b>Escolha uma época:</b>", markup=teclado_em_linhas(btns, 2))

    elif text == "🎲 Sugestão":
        d = tmdb("movie/top_rated", {"page":random.randint(1,20)})
        itens = (d or {}).get("results") or []
        novos = filtrar(cid, itens, "movie", permitir_repetir=False) or itens
        if not novos:
            await avisar_tmdb_vazio(context, cid)
            return
        item = random.choice(novos[:15])
        await send_item(context, cid, item, is_tv=False, tipo="movie", categoria="🎲 SUGESTÃO")
        await enviar(context, cid, text="Quer outra?", markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎲 Outra sugestão", callback_data="sugestao")]
        ]))
        await enviar_dica(context, cid)

    elif text == "🔍 Buscar":
        ia_txt = ""
        if AI_ENABLED:
            ia_txt = "\n<code>/ia sua pergunta</code> — converse com o assistente\n"
        await enviar(context, cid, text=(
            "⌨️ Busque assim:\n\n"
            "<code>/filme Nome do Filme</code>\n"
            "<code>/serie Nome da Série</code>\n"
            "<code>/ator Nome do Ator</code>\n"
            "<code>/top10</code> — mais vistos da semana\n"
            "<code>/indique</code> — ganhe +7 dias VIP\n"
            f"{ia_txt}\n"
            "O guia completo está em /comandos.\n"
            "Você também pode buscar em qualquer conversa: digite o @ do bot e o nome do filme."
        ))

    elif text == "❓ Ajuda":
        await cmd_ajuda_fn(context, cid)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    chat = update.effective_chat
    cid  = chat.id
    text = update.message.text
    user = update.effective_user
    uid  = user.id if user else 0

    # Captura o valor de depósito personalizado, se estivermos esperando
    if context.user_data.get("aguardando_valor_pix"):
        if chat.type != "private":
            return
        context.user_data["aguardando_valor_pix"] = False
        texto_valor = text.strip().replace("R$", "").replace(" ", "").replace(",", ".")
        try:
            valor = float(texto_valor)
        except ValueError:
            await enviar(context, cid, text=(
                "⚠️ Valor inválido. Use apenas números, ex: <code>47</code> ou <code>47,50</code>.\n"
                "Use /credito para tentar de novo."
            ))
            return
        if valor < 2.00:
            await enviar(context, cid, text=(
                "⚠️ O valor mínimo para depósito é <b>R$ 2,00</b>.\n"
                "Use /credito para tentar de novo."
            ))
            return
        await _gerar_e_enviar_pix(context, cid, uid, valor)
        return

    # IA: no grupo só se mencionou ou respondeu o bot; no privado, texto livre (se a IA estiver ligada).
    if text not in MENU_BOTOES:
        para_bot, pergunta_ia = mensagem_para_o_bot(update)
        if para_bot or (chat.type == "private" and AI_ENABLED and AI_API_KEY):
            await _entregar_ia(update, context, pergunta_ia or text)
            return
        if chat.type in ("group", "supergroup", "channel"):
            return

    # Em grupos, só reage aos botões do menu — nunca responde "acesso bloqueado" no meio do papo.
    if chat.type in ("group", "supergroup", "channel"):
        if text not in MENU_BOTOES:
            return
        if not acesso_conteudo(cid):
            return
        if not rate_ok(uid, "menu", GROUP_SEARCH_RATE_SECONDS):
            await avisar_aguarde(update)
            return
        await executar_menu(context, cid, text)
        return

    if not await verificar_acesso(update, context):
        return
    if text not in MENU_BOTOES:
        return
    if not rate_ok(uid, "menu", COMMAND_RATE_SECONDS):
        await avisar_aguarde(update)
        return
    await executar_menu(context, cid, text)

async def enviar_escolhas(context, chat_id, resultados, is_tv, query):
    if not resultados:
        tipo = "Série" if is_tv else "Filme"
        await enviar(context, chat_id, text=f"😕 {tipo} não encontrado: <b>{html.escape(query)}</b>")
        return
    if len(resultados) == 1:
        await send_item(context, chat_id, resultados[0], is_tv=is_tv, tipo="tv" if is_tv else "movie")
        return
    botoes = []
    kind = "tv" if is_tv else "movie"
    for item in resultados[:5]:
        title = item.get("name") if is_tv else item.get("title", "?")
        year = (item.get("first_air_date") if is_tv else item.get("release_date") or "")[:4]
        label = f"{title} ({year})" if year else (title or "?")
        if len(label) > 60:
            label = label[:57] + "…"
        botoes.append([InlineKeyboardButton(label, callback_data=f"pick:{kind}:{item.get('id')}")])
    await enviar(
        context, chat_id,
        text=f"🔍 Encontrei estes títulos para <b>{html.escape(query)}</b>. Qual você quer?",
        markup=InlineKeyboardMarkup(botoes),
    )

async def callback_start(update, context, acao):
    q = update.callback_query
    cid = update.effective_chat.id
    user = update.effective_user
    nome = (user.first_name if user else None) or "aí"
    if acao == "indique":
        await q.message.reply_text(
            "🎁 <b>Indique e ganhe +7 dias VIP</b>\n\n" + texto_indique(),
            parse_mode="HTML", reply_markup=markup_cta_app())
        return
    if acao == "lancamentos":
        if not rate_ok(user.id if user else 0, "menu", COMMAND_RATE_SECONDS):
            return
        d = tmdb("movie/now_playing", {"region": "BR"})
        if d and d.get("results"):
            await enviar_lista(context, cid, d.get("results", []), tipo="now_playing")
        else:
            await avisar_tmdb_vazio(context, cid)
        return
    if acao == "saas":
        bot_info = await context.bot.get_me()
        await q.message.reply_text(
            texto_saas(bot_info.username), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Suporte", url=CANAL_SUPORTE)],
            ]))
        return
    if acao == "home":
        await q.message.reply_text(
            texto_start_app(nome), parse_mode="HTML", reply_markup=markup_start_privado())

async def callback_handler(update, context):
    q = update.callback_query
    if not q:
        return
    data = q.data or ""
    chat = update.effective_chat
    cid = chat.id if chat else 0
    user = update.effective_user
    uid = user.id if user else 0

    if data.startswith("start:"):
        await q.answer()
        if chat and chat.type != "private":
            return
        await callback_start(update, context, data.split(":", 1)[1])
        return

    if data.startswith("pick:") or data.startswith("ver:"):
        partes = data.split(":")
        if len(partes) != 3:
            await q.answer()
            return
        _, kind, sid = partes
        if not (acesso_conteudo(cid) or (chat and chat.type == "private" and PUBLIC_SEARCH)):
            await q.answer("Abra o bot no privado para ver este título.", show_alert=True)
            return
        segundos = GROUP_SEARCH_RATE_SECONDS if (chat and chat.type in ("group", "supergroup")) else COMMAND_RATE_SECONDS
        if not rate_ok(uid, "search", segundos):
            await q.answer("Aguarde uns segundos…", show_alert=False)
            return
        await q.answer()
        try:
            iid = int(sid)
        except ValueError:
            return
        is_tv = kind == "tv"
        details = tmdb_details(iid, is_tv=is_tv)
        if not details:
            await enviar(context, cid, text="😕 Não consegui abrir este título agora.")
            return
        await send_item(context, cid, details, is_tv=is_tv, tipo="tv" if is_tv else "movie",
                        categoria=categoria_padrao(is_tv))
        return

    if data.startswith("pg:"):
        partes = data.split(":")
        if len(partes) != 3:
            await q.answer()
            return
        _, lid, spage = partes
        if not (acesso_conteudo(cid) or (chat and chat.type == "private" and PUBLIC_SEARCH)):
            await q.answer("Abra o bot no privado para ver isto.", show_alert=True)
            return
        await q.answer()
        try:
            page = int(spage)
        except ValueError:
            return
        await enviar_vitrine(context, cid, [], page=page, lista_id=lid)
        return

    if data == "sugestao":
        if not (acesso_conteudo(cid) or (chat and chat.type == "private" and PUBLIC_SEARCH)):
            await q.answer("Abra o bot no privado.", show_alert=True)
            return
        if not rate_ok(uid, "menu", COMMAND_RATE_SECONDS):
            await q.answer("Aguarde uns segundos…")
            return
        await q.answer()
        await executar_menu(context, cid, "🎲 Sugestão")
        return

    # Gênero / época
    if not (acesso_conteudo(cid) or (chat and chat.type == "private" and PUBLIC_SEARCH)):
        await q.answer("Abra o bot no privado para usar este menu.", show_alert=True)
        return
    await q.answer()
    if not rate_ok(uid, "menu", COMMAND_RATE_SECONDS):
        return

    if data.startswith("gen_"):
        gid = data.split("_", 1)[1]
        d = tmdb("discover/movie", {"with_genres":gid,"sort_by":"popularity.desc","page":random.randint(1,5)})
        nome = next((n for n,i in GENEROS.items() if str(i)==str(gid)), "Gênero")
        await enviar_vitrine(context, cid, (d or {}).get("results") or [],
                             categoria="🎬 FILME", titulo=f"✨ {nome}")

    elif data.startswith("era_"):
        era = data.split("_", 1)[1]
        if era not in EPOCAS:
            return
        inicio, fim = EPOCAS[era]
        ano = random.randint(inicio, fim)
        d = tmdb("discover/movie", {"primary_release_year":ano,"sort_by":"popularity.desc","page":1})
        await enviar_vitrine(context, cid, (d or {}).get("results") or [],
                             categoria="🎬 FILME", titulo=f"🎞️ Destaques de {ano}")

# ── Comandos com verificação de acesso ────────────────────────────────────
async def _guard_busca(update, context) -> bool:
    if not update.message:
        return False
    if not await verificar_acesso(update, context, silent=is_grupo(update)):
        return False
    user = update.effective_user
    uid = user.id if user else 0
    segundos = GROUP_SEARCH_RATE_SECONDS if is_grupo(update) else COMMAND_RATE_SECONDS
    if not rate_ok(uid, "search", segundos):
        await avisar_aguarde(update)
        return False
    return True

async def cmd_filme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard_busca(update, context):
        return
    if not context.args:
        await update.message.reply_text("⚠️ Use: /filme Nome do Filme"); return
    cid = update.effective_chat.id
    q   = " ".join(context.args)
    d   = tmdb("search/movie", {"query": q})
    res = d.get("results",[]) if d else []
    await enviar_escolhas(context, cid, res, is_tv=False, query=q)

async def cmd_serie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard_busca(update, context):
        return
    if not context.args:
        await update.message.reply_text("⚠️ Use: /serie Nome da Série"); return
    cid = update.effective_chat.id
    q   = " ".join(context.args)
    d   = tmdb("search/tv", {"query": q})
    res = d.get("results",[]) if d else []
    await enviar_escolhas(context, cid, res, is_tv=True, query=q)

async def cmd_ator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard_busca(update, context):
        return
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
    if not await _guard_busca(update, context):
        return
    cid = update.effective_chat.id
    d   = tmdb("trending/all/week")
    if not d or not d.get("results"):
        await enviar(context, cid, text="😕 Não foi possível buscar o Top 10."); return
    itens  = d["results"][:10]
    linhas = ["🏆 <b>Mais vistos da semana:</b>\n"]
    for i, item in enumerate(itens, 1):
        is_tv = item.get("media_type") == "tv"
        name  = item.get("name") if is_tv else item.get("title","?")
        ano   = (item.get("first_air_date","") if is_tv else item.get("release_date",""))[:4]
        nota  = item.get("vote_average",0)
        tipo  = "📺" if is_tv else "🎬"
        linhas.append(f"{i}. {tipo} {html.escape(name)} ({ano}) — ⭐{nota:.1f}")
    await enviar(context, cid, text="\n".join(linhas), markup=markup_cta_app())

def texto_tutorial(bot_username=None):
    uname = bot_username or _bot_username or "StreamFlixVip_Bot"
    ia_bloco = ""
    if AI_ENABLED:
        ia_bloco = (
            "\n🤖 <b>Assistente</b>\n"
            "<code>/ia um filme de comédia para hoje</code>\n"
            f"Ou me mencione no grupo: <code>@{html.escape(uname)} indica um terror</code>\n"
        )
    return (
        "👋 <b>Como usar o StreamFlix VIP</b>\n\n"
        "1️⃣ No privado, toque nos botões do menu (Em Cartaz, Séries, Sugestão…).\n"
        "Você recebe um card bonito e mais títulos para abrir. Toque em <b>Mais ▶️</b> para ver o resto.\n\n"
        "2️⃣ Para buscar um nome específico:\n"
        "<code>/filme Duna</code>\n"
        "<code>/serie The Last of Us</code>\n"
        "<code>/ator Zendaya</code>\n"
        "<code>/top10</code> — os mais vistos da semana\n\n"
        "3️⃣ Baixe o app e ganhe bônus:\n"
        f"{texto_indique()}\n"
        f"🌐 {html.escape(ensure_https(SITE_URL))}\n"
        f"{ia_bloco}\n"
        "🔎 Em qualquer conversa você também pode digitar\n"
        f"<code>@{html.escape(uname)} nome do filme</code>\n\n"
        f"💬 Suporte: {CANAL_SUPORTE}"
    )

async def cmd_ajuda_fn(context, cid, bot_username=None):
    await enviar(context, cid, text=texto_tutorial(bot_username), markup=markup_cta_app())

async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if is_grupo(update) and not acesso_conteudo(update.effective_chat.id):
        return
    uname = _bot_username
    try:
        uname = uname or (await context.bot.get_me()).username
    except Exception:
        pass
    await cmd_ajuda_fn(context, update.effective_chat.id, uname)

async def cmd_comandos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_ajuda(update, context)

async def cmd_ia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    pergunta = " ".join(context.args).strip() if context.args else ""
    await _entregar_ia(update, context, pergunta)

# ── Perfil, comandos e modo inline ────────────────────────────────────────
BOT_SHORT_DESCRIPTION_PADRAO = (
    "Filmes, séries e TV no StreamFlix. Baixe o app, busque títulos e ganhe +7 dias VIP indicando amigos."
)
BOT_DESCRIPTION_PADRAO = (
    "O StreamFlix Bot te ajuda a encontrar filmes e séries e a baixar o app.\n\n"
    "🌐 Site: https://www.streamflixvip.online\n\n"
    "📱 Baixe o app (Downloader):\n"
    "• Celular: 6085325\n"
    "• TV: 3422972\n\n"
    "🎁 Indique e ganhe +7 dias VIP\n\n"
    "O que você pode fazer:\n"
    "• Buscar filme, série ou ator\n"
    "• Ver os mais assistidos da semana\n"
    "• Receber lançamentos e enquetes no grupo\n"
    "• Falar com o suporte\n\n"
    "No privado, toque em /start para baixar o app e começar."
)

def comandos_privado():
    return [
        BotCommand("start", "Abrir o menu e baixar o app"),
        BotCommand("filme", "Buscar um filme"),
        BotCommand("serie", "Buscar uma série"),
        BotCommand("ator", "Filmes de um ator ou atriz"),
        BotCommand("top10", "Mais vistos da semana"),
        BotCommand("indique", "Indique e ganhe +7 dias VIP"),
        BotCommand("comandos", "Guia rápido de como usar"),
        BotCommand("ia", "Perguntar ao assistente"),
        BotCommand("credito", "Saldo, PIX e resgates"),
        BotCommand("ajuda", "Como usar o bot"),
        BotCommand("meuplano", "Ver o plano do bot no canal"),
    ]

def comandos_grupo():
    return [
        BotCommand("filme", "Buscar um filme"),
        BotCommand("serie", "Buscar uma série"),
        BotCommand("top10", "Mais vistos da semana"),
        BotCommand("indique", "Indique e ganhe +7 dias VIP"),
        BotCommand("comandos", "Guia rápido de como usar"),
        BotCommand("ia", "Perguntar ao assistente"),
        BotCommand("ajuda", "Como usar o bot"),
    ]

def comandos_admin():
    return comandos_privado() + [
        BotCommand("gerar", "Gerar tokens de ativação"),
        BotCommand("clientes", "Ver clientes do bot"),
        BotCommand("renovar", "Renovar um cliente"),
        BotCommand("revogar", "Revogar um cliente"),
        BotCommand("stats", "Números do bot"),
        BotCommand("config", "Modo e site do cliente"),
    ]

async def configurar_comandos(bot):
    await bot.set_my_commands(comandos_privado(), scope=BotCommandScopeDefault())
    await bot.set_my_commands(comandos_privado(), scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(comandos_grupo(), scope=BotCommandScopeAllGroupChats())
    if ADMIN_ID:
        await bot.set_my_commands(comandos_admin(), scope=BotCommandScopeChat(chat_id=ADMIN_ID))

def texto_perfil_curto():
    return (os.environ.get("BOT_SHORT_DESCRIPTION") or BOT_SHORT_DESCRIPTION_PADRAO).strip()

def texto_perfil_longo():
    custom = (os.environ.get("BOT_DESCRIPTION") or "").strip()
    if custom:
        return custom
    return (
        "O StreamFlix Bot te ajuda a encontrar filmes e séries e a baixar o app.\n\n"
        f"🌐 Site: {ensure_https(SITE_URL)}\n\n"
        "📱 Baixe o app (Downloader):\n"
        f"• Celular: {DOWNLOADER_CELULAR}\n"
        f"• TV: {DOWNLOADER_TV}\n\n"
        "🎁 Indique e ganhe +7 dias VIP\n\n"
        "O que você pode fazer:\n"
        "• Buscar filme, série ou ator\n"
        "• Ver os mais assistidos da semana\n"
        "• Receber lançamentos e enquetes no grupo\n"
        "• Falar com o suporte\n\n"
        "No privado, toque em /start para baixar o app e começar."
    )

async def configurar_perfil(bot):
    short = texto_perfil_curto()
    desc  = texto_perfil_longo()
    if short:
        await bot.set_my_short_description(short[:120])
    if desc:
        await bot.set_my_description(desc[:512])

async def limpar_teclado_grupos(bot):
    """Remove o teclado fixo antigo dos grupos (a mensagem some sozinha em seguida)."""
    for cid in chats_destinatarios():
        try:
            chat = await bot.get_chat(cid)
            if chat.type not in ("group", "supergroup"):
                continue
            kw = {}
            try:
                m = await bot.send_message(cid, "✅ Bot atualizado! Use o menu / ou /comandos.",
                                           reply_markup=ReplyKeyboardRemove(), disable_notification=True)
            except Exception:
                if not TOPIC_ID:
                    raise
                m = await bot.send_message(cid, "✅ Bot atualizado! Use o menu / ou /comandos.",
                                           reply_markup=ReplyKeyboardRemove(), disable_notification=True,
                                           message_thread_id=TOPIC_ID)
            await asyncio.sleep(5)
            try:
                await bot.delete_message(cid, m.message_id)
            except Exception:
                pass
            logging.info(f"Teclado removido no chat {cid}")
        except Exception as e:
            logging.warning(f"Limpar teclado falhou em {cid}: {e}")

async def post_init(application):
    try:
        global _bot_username
        try:
            me = await application.bot.get_me()
            _bot_username = me.username or ""
        except Exception:
            _bot_username = ""
        await configurar_comandos(application.bot)
        logging.info("Menu de comandos atualizado (pt-BR).")
    except Exception as e:
        logging.warning(f"Não foi possível configurar o menu de comandos: {e}")
    if os.environ.get("CLEAR_GROUP_KEYBOARD", "1") == "1":
        try:
            await limpar_teclado_grupos(application.bot)
        except Exception as e:
            logging.warning(f"Não foi possível limpar o teclado dos grupos: {e}")
    if SET_BOT_PROFILE:
        try:
            await configurar_perfil(application.bot)
            logging.info("Descrição do bot atualizada (SET_BOT_PROFILE=1).")
        except Exception as e:
            logging.warning(f"Não foi possível atualizar a descrição do bot: {e}")

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not INLINE_MODE or not update.inline_query:
        return
    iq = update.inline_query
    uid = iq.from_user.id if iq.from_user else 0
    q = (iq.query or "").strip()
    if len(q) < 2:
        await iq.answer(
            [], cache_time=10, is_personal=False,
            switch_pm_text="Abrir o StreamFlix Bot",
            switch_pm_parameter="inline",
        )
        return
    if not rate_ok(uid, "inline", 2):
        await iq.answer([], cache_time=1, is_personal=True)
        return
    d = tmdb("search/multi", {"query": q}) or {}
    resultados = []
    for item in d.get("results") or []:
        media = item.get("media_type")
        if media not in ("movie", "tv"):
            continue
        is_tv = media == "tv"
        title = item.get("name") if is_tv else item.get("title") or "?"
        year = (item.get("first_air_date") if is_tv else item.get("release_date") or "")[:4]
        poster = item.get("poster_path")
        sinopse = (item.get("overview") or "").strip()
        if len(sinopse) > 180:
            sinopse = sinopse[:180].rsplit(" ", 1)[0] + "…"
        caption = f"{'📺' if is_tv else '🎬'} <b>{html.escape(title)}</b>"
        if year:
            caption += f" ({html.escape(year)})"
        if sinopse:
            caption += f"\n\n{html.escape(sinopse)}"
        site = ensure_https(SITE_URL)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ Assista no StreamFlix", url=site)],
            [InlineKeyboardButton("📱 Baixar app", url=link_app_download())],
        ])
        rid = f"{media}-{item.get('id')}"
        titulo_r = f"{title} ({year})" if year else title
        desc = sinopse or ("Série" if is_tv else "Filme")
        if poster:
            resultados.append(InlineQueryResultPhoto(
                id=rid,
                photo_url=f"{IMG_BASE}{poster}",
                thumbnail_url=f"https://image.tmdb.org/t/p/w92{poster}",
                title=titulo_r[:64],
                description=desc[:120],
                caption=caption[:1024],
                parse_mode="HTML",
                reply_markup=kb,
            ))
        else:
            resultados.append(InlineQueryResultArticle(
                id=rid,
                title=titulo_r[:64],
                description=desc[:120],
                input_message_content=InputTextMessageContent(caption[:4096], parse_mode="HTML"),
                reply_markup=kb,
            ))
        if len(resultados) >= 8:
            break
    await iq.answer(
        resultados, cache_time=30, is_personal=False,
        switch_pm_text="Abrir o StreamFlix Bot",
        switch_pm_parameter="inline",
    )


# ── Main ───────────────────────────────────────────────────────────────────
def main():
    setup_db()
    threading.Thread(target=start_health, daemon=True).start()
    app = Application.builder().token(TOKEN).post_init(post_init).build()

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
    app.add_handler(CommandHandler("indique",  cmd_indique))
    app.add_handler(CommandHandler("comandos", cmd_comandos))
    app.add_handler(CommandHandler("tutorial", cmd_comandos))
    app.add_handler(CommandHandler("ia",       cmd_ia))

    # Painel admin (só você usa — protegido por ADMIN_ID)
    app.add_handler(CommandHandler("gerar",    cmd_gerar))
    app.add_handler(CommandHandler("clientes", cmd_clientes))
    app.add_handler(CommandHandler("renovar",  cmd_renovar))
    app.add_handler(CommandHandler("revogar",  cmd_revogar))
    app.add_handler(CommandHandler("stats",    cmd_stats))
    app.add_handler(CommandHandler("config",   cmd_config))

    # Créditos
    app.add_handler(CommandHandler("credito", cmd_credito))
    app.add_handler(CallbackQueryHandler(callback_credito, pattern="^(pix:|pix_custom|check:|resgatar:|confirmar:|cancelar|voltar_credito)"))
    # Texto, callbacks e modo inline
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(InlineQueryHandler(inline_query))
    # Boas-vindas (serviço + chat_member; rate-limit evita flood)
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_chat_members))
    app.add_handler(ChatMemberHandler(on_chat_member, ChatMemberHandler.CHAT_MEMBER))

    # Jobs automáticos
    jq = app.job_queue
    if jq:
        manha_h = max(0, min(23, MANHA_HOUR_UTC))
        noite_h = max(0, min(23, NOITE_HOUR_UTC))
        jq.run_daily(job_diario_manha, time=datetime.strptime(f"{manha_h:02d}:00","%H:%M").time())  # padrão 8h Fortaleza
        jq.run_daily(job_diario_noite, time=datetime.strptime(f"{noite_h:02d}:00","%H:%M").time())  # padrão 20h Fortaleza
        jq.run_repeating(job_verificar_vencimentos, interval=3600, first=60)                       # a cada 1h
        # Propaganda: padrão 18:00 UTC (15h Fortaleza). Antes eram 13,18,22.
        # PROPAGANDA_ENABLED=0 (padrão): o post do app das 17h já cobre a divulgação
        for _h in (parse_horas_utc(PROPAGANDA_HOURS_UTC, [18]) if os.environ.get("PROPAGANDA_ENABLED", "0") == "1" else []):
            jq.run_daily(job_propaganda, time=datetime.strptime(f"{_h:02d}:00","%H:%M").time())
        # Novos jobs (horários em UTC, iguais aos existentes: UTC = BRT+3)
        promo_h = max(0, min(23, APP_PROMO_HOUR_UTC))
        poll_h  = max(0, min(23, POLL_HOUR_UTC))
        weekday = max(0, min(6, POLL_WEEKDAY))
        jq.run_daily(job_app_promo, time=datetime.strptime(f"{promo_h:02d}:00","%H:%M").time())  # padrão 17h BRT
        jq.run_daily(job_enquete_semanal, time=datetime.strptime(f"{poll_h:02d}:00","%H:%M").time(), days=(weekday,))  # padrão sexta 18h BRT

    # Handler de erro global: evita que um Conflict (comum durante rolling
    # deploy do Koyeb — duas instâncias tentando getUpdates por alguns
    # segundos) derrube a Application inteira. O PTB já tenta de novo
    # sozinho; só precisamos não deixar a exceção subir e matar o loop.
    async def _on_error(update, context):
        err = context.error
        from telegram.error import Conflict
        if isinstance(err, Conflict):
            logging.warning("Conflict (getUpdates) — provavelmente rolling deploy trocando instância, ignorando.")
            return
        logging.error(f"Erro não tratado: {err}")
    app.add_error_handler(_on_error)

    logging.info(f"✅ Bot v8.3 SaaS Online — {SITE_URL}")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            # Espera mais tempo antes de tentar de novo — dá tempo da
            # instância antiga (rolling deploy do Koyeb) sair de vez e
            # liberar o getUpdates, em vez de entrar em loop de conflito.
            logging.error(f"💥 Reiniciando em 30s: {e}")
            time.sleep(30)