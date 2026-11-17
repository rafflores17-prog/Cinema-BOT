#!/usr/bin/env python3
"""Testes offline: migração de sent_items, chats inválidos/tópicos e flag do teclado."""
import asyncio, types
import psycopg2
import bot

class FakeCur:
    def __init__(self, db): self.db = db; self.rowcount = 0; self._rows = []
    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        self.db.log.append(s)
        if "information_schema.columns" in s:
            self._rows = self.db.cols
        elif s.startswith("CREATE UNIQUE INDEX") and self.db.dup:
            raise psycopg2.IntegrityError("could not create unique index")
        elif s.startswith("UPDATE sent_items"):
            self.rowcount = 0
        elif s.startswith("INSERT INTO sent_items") and self.db.pk_old:
            raise psycopg2.IntegrityError("duplicate key")
    def fetchall(self): return self._rows
    def fetchone(self): return None
    def close(self): pass
class FakeConn:
    def __init__(self, cols, dup=False, pk_old=False):
        self.cols, self.dup, self.pk_old, self.log = cols, dup, pk_old, []
    def cursor(self): return FakeCur(self)
    def commit(self): self.log.append("COMMIT")
    def rollback(self): self.log.append("ROLLBACK")
    def close(self): pass

# 1) tabela antiga só com (chat_id, item_id)
old = [("chat_id", "bigint", "NO", None), ("item_id", "bigint", "NO", None)]
c = FakeConn(old)
bot.migrar_sent_items(c)
joined = "\n".join(c.log)
assert "CREATE TABLE IF NOT EXISTS sent_items_bak_20261117 AS SELECT * FROM sent_items" in joined
assert joined.index("sent_items_bak_20261117") < joined.index("ADD COLUMN IF NOT EXISTS item_type")
assert "ADD COLUMN IF NOT EXISTS sent_at" in joined and "CREATE UNIQUE INDEX" in joined
assert bot._SENT_UPSERT_OK[0] is True and "DROP" not in joined.upper()
print("migração antiga OK")

# 2) tabela nova: sem backup nem ALTER
new = old + [("item_type", "text", "NO", None), ("sent_at", "timestamp", "NO", None)]
c = FakeConn(new)
bot.migrar_sent_items(c)
assert "bak" not in "\n".join(c.log) and "ALTER" not in "\n".join(c.log)
print("tabela nova OK")

# 3) índice bloqueado por duplicatas -> fallback UPDATE/INSERT, e PK antiga -> UPDATE só por chat/item
c = FakeConn(old, dup=True)
bot.migrar_sent_items(c)
assert bot._SENT_UPSERT_OK[0] is False
c2 = FakeConn(old, pk_old=True)
bot.db = lambda: c2
bot.marcar_enviado(-1, 99, "movie")
j = "\n".join(c2.log)
assert "INSERT INTO sent_items (chat_id, item_id, item_type, sent_at)" in j and "ROLLBACK" in j
assert "UPDATE sent_items SET sent_at=%s WHERE chat_id=%s AND item_id=%s" in j
print("fallback sem índice OK")
bot._SENT_UPSERT_OK[0] = True
c3 = FakeConn(new); bot.db = lambda: c3
bot.marcar_enviado(-1, 99, "tv")
assert "ON CONFLICT (chat_id, item_id, item_type)" in "\n".join(c3.log)

# 4) envio: tópico inexistente -> reenvia sem tópico; chat não encontrado -> pula depois
class BadRequest(Exception): pass
calls = []
class FakeBot:
    async def send_message(self, chat_id, text, **kw):
        calls.append((chat_id, kw.get("message_thread_id")))
        if chat_id == -1003177664821:
            raise BadRequest("Chat not found")
        if kw.get("message_thread_id"):
            raise BadRequest("Message thread not found")
        return types.SimpleNamespace(message_id=1)
ctx = types.SimpleNamespace(bot=FakeBot())
bot.get_topic_id = lambda cid: 55 if cid == -1003083067544 else 0
async def run():
    r = await bot.enviar(ctx, -1003083067544, text="oi")
    assert r and calls == [(-1003083067544, 55), (-1003083067544, None)]
    calls.clear()
    await bot.enviar(ctx, -1003083067544, text="oi")
    assert calls == [(-1003083067544, None)]          # lembra que o tópico não existe
    calls.clear()
    assert await bot.enviar(ctx, -1003177664821, text="oi") is None
    assert await bot.enviar(ctx, -1003177664821, text="oi") is None
    assert len(calls) == 1 and bot.chat_morto(-1003177664821)
asyncio.run(run())
print("chats inválidos/tópicos OK")

# 5) limpeza do teclado: só uma vez por versão; sem banco -> não posta
posted = []
class B2:
    async def get_chat(self, cid): posted.append(cid); return types.SimpleNamespace(type="channel")
bot.chats_destinatarios = lambda: [-100]
bot.kv_get = lambda k: bot.KEYBOARD_CLEAN_VERSION
asyncio.run(bot.limpar_teclado_grupos(B2())); assert posted == []
def boom(k): raise RuntimeError("sem banco")
bot.kv_get = boom
asyncio.run(bot.limpar_teclado_grupos(B2())); assert posted == []
saved = {}
bot.kv_get = lambda k: None; bot.kv_set = lambda k, v: saved.update({k: v})
asyncio.run(bot.limpar_teclado_grupos(B2())); assert posted == [-100] and saved
print("flag do teclado OK")
print("OK: ops_test")
