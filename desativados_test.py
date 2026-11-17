#!/usr/bin/env python3
"""Teste offline dos destinos desativados (bot_kv + DISABLED_CHAT_IDS)."""
import sys, os, json, asyncio, threading, types, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DISABLED_CHAT_IDS"] = "-100555"
import bot
from http.server import ThreadingHTTPServer

KV = {}
bot.kv_get = lambda k: KV.get(k)
def kv_set(k, v): KV[k] = v
bot.kv_set = kv_set
VELHO, NOVO, OUTRO = -1003083067544, -1004378949622, -1002707666244
bot.GRUPO_ID, bot.CANAL_VIP = NOVO, VELHO
bot._desat["ids"] = None

# semente: primeira leitura grava o padrão no bot_kv
assert bot.chat_desativado(VELHO) and json.loads(KV["disabled_chat_ids"]) == [VELHO]
assert bot.chat_desativado(-100555)                     # env
assert not bot.chat_desativado(NOVO)
assert bot.chat_morto(VELHO) and not bot.chat_oficial(VELHO) and bot.chat_oficial(NOVO)
assert bot.sem_desativados([NOVO, VELHO, -100555, 0]) == [NOVO]
bot.WELCOME_INCLUDE_CLIENTS = False
assert VELHO not in bot.chats_boas_vindas() and NOVO in bot.chats_boas_vindas()
bot.db = lambda: (_ for _ in ()).throw(RuntimeError("sem banco"))
assert bot.chats_destinatarios() == [NOVO]

# envios: propaganda agendada, envio direto e enviar()
enviados = []
class FakeBot:
    async def send_message(self, chat_id, text=None, **kw):
        enviados.append(chat_id)
    async def send_photo(self, chat_id, *a, **kw):
        enviados.append(chat_id)
    async def get_chat(self, chat_id):
        return types.SimpleNamespace(title="G", username="", type="supergroup")
ctx = types.SimpleNamespace(bot=FakeBot())
bot.get_topic_id = lambda c: 0
bot.PROPAGANDA_USE_DB = False
bot.get_proximo_idx = lambda: 0
asyncio.run(bot.job_propaganda(ctx))
assert enviados == [NOVO], enviados
enviados.clear()
asyncio.run(bot._send_ativo(ctx.bot, VELHO, "oi"))
asyncio.run(bot.enviar(ctx, VELHO, text="oi"))
assert enviados == []

# painel: destinos, desativar e reativar
loop = asyncio.new_event_loop()
threading.Thread(target=loop.run_forever, name="app-loop", daemon=True).start()
bot._APP[0], bot._APP[1] = types.SimpleNamespace(bot=FakeBot()), loop
bot.PANEL_PASS = "s"
srv = ThreadingHTTPServer(("127.0.0.1", 0), bot.AdminHandler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_address[1]}/admin"
def post(body):
    req = urllib.request.Request(base, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "X-Admin-Pass": "s"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())
d = post({"cmd": "destinos"})
assert [x["chat_id"] for x in d["destinos"]] == [NOVO], d
ds = {x["chat_id"]: x for x in d["desativados"]}
assert VELHO in ds and ds[-100555]["fixo"] and not ds[VELHO]["fixo"]
d = post({"cmd": f"destino_desativar:{OUTRO}"})
assert d["ok"] and OUTRO in json.loads(KV["disabled_chat_ids"]) and -100555 not in json.loads(KV["disabled_chat_ids"])
assert bot.chat_desativado(OUTRO)
d = post({"cmd": f"destino_reativar:{OUTRO}"})
assert d["ok"] and not bot.chat_desativado(OUTRO)
d = post({"cmd": "destino_reativar:-100555"})
assert not d["ok"] and "DISABLED_CHAT_IDS" in d["error"]
d = post({"cmd": f"destino_reativar:{VELHO}"})          # dá para reativar o padrão; não volta sozinho
assert d["ok"] and not bot.chat_desativado(VELHO) and json.loads(KV["disabled_chat_ids"]) == []
bot._desat["ids"] = None
assert not bot.chat_desativado(VELHO)
d = post({"cmd": f"destino_desativar:{VELHO}"})
d = post({"cmd": "propaganda_disparo", "texto": "x", "chat_ids": [VELHO, NOVO]})
assert d["total"] == 1 and d["enviados"] == 1, d
srv.shutdown()
print("OK: desativados_test")
