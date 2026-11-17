#!/usr/bin/env python3
"""Teste offline da API do painel: servidor HTTP real + bot simulado no loop da aplicação."""
import sys, os, json, asyncio, threading, types, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bot
from http.server import ThreadingHTTPServer

bot.PANEL_PASS = "segredo-teste"
bot.chats_destinatarios = lambda: [-1004378949622, -1002707666244, -1003177664821]
bot.get_topic_id = lambda c: 77 if c == -1002707666244 else 0
enviados = []
class BadRequest(Exception): pass
class FakeBot:
    async def send_message(self, chat_id, text, **kw):
        assert threading.current_thread().name == "app-loop", "envio fora do loop da aplicação"
        if chat_id == -1003177664821:
            raise BadRequest("Chat not found")
        if kw.get("message_thread_id"):
            raise BadRequest("Message thread not found")
        if kw.get("parse_mode") == "HTML" and "<x" in text:
            raise BadRequest("Can't parse entities: unsupported start tag")
        enviados.append((chat_id, text, kw.get("parse_mode")))
loop = asyncio.new_event_loop()
threading.Thread(target=loop.run_forever, name="app-loop", daemon=True).start()
bot._APP[0], bot._APP[1] = types.SimpleNamespace(bot=FakeBot()), loop

srv = ThreadingHTTPServer(("127.0.0.1", 0), bot.AdminHandler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_address[1]}/admin"

def post(body, senha="segredo-teste"):
    req = urllib.request.Request(base, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "X-Admin-Pass": senha,
                 "Origin": "https://cinema-bot-painel.vercel.app"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read()), r.headers.get("Access-Control-Allow-Origin")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()), None

st, d, cors = post({"cmd": "propaganda_disparo", "texto": "🎬 Promo {contato} com chaves {x} e <b>negrito</b>"})
print(st, d, cors)
assert st == 200 and d["ok"] and d["enviados"] == 2 and d["total"] == 3
assert d["falhas"][0]["chat_id"] == -1003177664821 and "not found" in d["falhas"][0]["erro"]
assert cors == "https://cinema-bot-painel.vercel.app"
assert any(c == -1002707666244 for c, _, _ in enviados)          # tópico inexistente -> reenviou sem tópico
assert all("@" in t and "{x}" in t for _, t, _ in enviados)
enviados.clear()
st, d, _ = post({"cmd": "propaganda_disparo", "texto": "texto <x> quebrado"})
assert d["enviados"] == 2 and all(p is None for *_, p in enviados)  # HTML inválido -> texto puro
enviados.clear()
st, d, _ = post({"cmd": "propaganda_disparo"})                      # sem texto -> texto padrão do app
assert d["enviados"] == 2 and enviados[0][1]
st, d, _ = post({"cmd": "propaganda_disparo"}, senha="errada")
assert st == 403
# legado via GET
enviados.clear()
from urllib.parse import quote
req = urllib.request.Request(base + "?cmd=" + quote("propaganda_disparo:" + quote("Olá via GET")),
                             headers={"X-Admin-Pass": "segredo-teste"})
with urllib.request.urlopen(req, timeout=20) as r:
    d = json.loads(r.read())
assert d["enviados"] == 2 and enviados[0][1] == "Olá via GET"
print("OK: panel_test")
srv.shutdown()

# ---- destinos, seleção e configs ----
srv = ThreadingHTTPServer(("127.0.0.1", 0), bot.AdminHandler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_address[1]}/admin"
bot.destinos_painel = lambda: [{"chat_id": -1004378949622, "nome": "FILMOW_ONDI", "origem": "cliente"},
                               {"chat_id": -1002707666244, "nome": "", "origem": "cliente"}]
async def fake_get_chat(chat_id):
    if chat_id == -1002707666244:
        raise BadRequest("Chat not found")
    return types.SimpleNamespace(title="StreamFlix VIP Filmes", username="streamflixvipfilmes", type="supergroup")
FakeBot.get_chat = staticmethod(fake_get_chat)
st, d, _ = post({"cmd": "destinos"})
print(d)
assert d["destinos"][0]["acessivel"] and d["destinos"][0]["titulo"] == "StreamFlix VIP Filmes"
assert d["destinos"][1]["acessivel"] is False
enviados.clear()
st, d, _ = post({"cmd": "propaganda_disparo", "texto": "Só no grupo novo", "chat_ids": [-1004378949622, -999]})
assert d["enviados"] == 1 and d["total"] == 1 and enviados[0][0] == -1004378949622   # -999 não permitido
bot.set_modo = lambda cid, modo: modo == "simples"
st, d, _ = post({"cmd": "config_modo:-1004378949622:basico"})
assert d["ok"] and d["modo"] == "simples"
st, d, _ = post({"cmd": "config_site:-1004378949622:ftp%3A%2F%2Fx"})
assert not d["ok"] and "http" in d["error"]
print("OK: panel_test destinos/config")
srv.shutdown()
