#!/usr/bin/env python3
"""Testes offline: migração de sent_items, chats inválidos/tópicos e flag do teclado."""
import asyncio, types
import psycopg2
import bot

class FakeCur:
    def __init__(self, db): self.db = db; self.rowcount = 0; self._rows = []; self._one = None
    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        self.db.log.append((s, params))
        d = self.db
        if "information_schema.columns" in s:
            self._rows = [(c, "x", "NO", None) for c in d.cols]
        elif "to_regclass" in s:
            self._one = (d.bak,)
        elif s.startswith("CREATE TABLE IF NOT EXISTS sent_items_bak"):
            d.bak = True
        elif s.startswith("SELECT COUNT(*)"):
            self._one = (42,)
        elif s.startswith("ALTER TABLE sent_items ADD COLUMN"):
            col = s.split("IF NOT EXISTS ")[1].split()[0]
            if col in d.alter_fail:
                raise psycopg2.ProgrammingError("permission denied")
            d.cols.append(col)
        elif s.startswith("CREATE UNIQUE INDEX"):
            if d.dup or not {"chat_id", "item_id", "item_type"} <= set(d.cols):
                raise psycopg2.IntegrityError("could not create unique index")
        elif s.startswith("UPDATE sent_items"):
            self.rowcount = 0
        elif s.startswith("INSERT INTO sent_items") and d.pk_old:
            raise psycopg2.IntegrityError("duplicate key")
        elif s.startswith("SELECT item_id FROM sent_items"):
            self._rows = [(1,), (2,)]
    def fetchall(self): return self._rows
    def fetchone(self): return self._one
    def close(self): pass
class FakeConn:
    def __init__(self, cols, dup=False, pk_old=False, alter_fail=()):
        self.cols, self.dup, self.pk_old, self.log = list(cols), dup, pk_old, []
        self.bak, self.alter_fail = False, set(alter_fail)
    def cursor(self): return FakeCur(self)
    def commit(self): self.log.append(("COMMIT", None))
    def rollback(self): self.log.append(("ROLLBACK", None))
    def close(self): pass
    def sql(self): return "\n".join(x[0] for x in self.log)

# 1) produção: sem chat_id
prod = ["item_id", "item_type", "sent_at"]
c = FakeConn(prod, dup=True)
bot.migrar_sent_items(c)
j = c.sql()
assert j.index("sent_items_bak_20261117 AS SELECT") < j.index("ADD COLUMN IF NOT EXISTS chat_id BIGINT NOT NULL DEFAULT 0")
assert "DROP" not in j.upper() and "chat_id" in bot._SENT_COLS and bot._SENT_UPSERT_OK[0] is False
bot.db = lambda: c
c.log.clear()
assert bot.ids_enviados(-5) >= {1, 2}
sel = [x for x in c.log if x[0].startswith("SELECT item_id")][0]
assert "(chat_id=%s OR chat_id=0)" in sel[0] and sel[1][0] == -5
c.log.clear(); bot.marcar_enviado(-5, 99, "movie")
assert "INSERT INTO sent_items (chat_id, item_id, item_type, sent_at)" in c.sql()
print("produção sem chat_id (com duplicatas) OK")

# 2) ALTER falha: continua sem chat_id, sem quebrar
c = FakeConn(prod, alter_fail={"chat_id"})
bot.migrar_sent_items(c)
assert "chat_id" not in bot._SENT_COLS and bot._SENT_UPSERT_OK[0] is False
bot.db = lambda: c
c.log.clear(); bot.ids_enviados(-5)
sel = [x for x in c.log if x[0].startswith("SELECT item_id")][0]
assert "chat_id" not in sel[0]
c.log.clear(); bot.marcar_enviado(-5, 99, "tv")
j = c.sql()
assert "INSERT INTO sent_items (item_id, item_type, sent_at)" in j and "chat_id" not in j
print("ALTER falhou -> funciona sem chat_id OK")

# 3) sem duplicatas: índice criado -> ON CONFLICT
c = FakeConn(prod)
bot.migrar_sent_items(c)
assert bot._SENT_UPSERT_OK[0] is True
bot.db = lambda: c; c.log.clear(); bot.marcar_enviado(-5, 7, "movie")
assert "ON CONFLICT (chat_id, item_id, item_type)" in c.sql()
# 4) tabela já nova: sem backup nem ALTER
c = FakeConn(["chat_id", "item_id", "item_type", "sent_at"])
bot.migrar_sent_items(c)
assert "bak" not in c.sql() and "ALTER" not in c.sql()
# 5) PK antiga curta -> rollback e UPDATE por item_id
bot._SENT_UPSERT_OK[0] = False
c = FakeConn(["chat_id", "item_id", "item_type", "sent_at"], pk_old=True)
bot._SENT_COLS.clear(); bot._SENT_COLS.update(c.cols)
bot.db = lambda: c; bot.marcar_enviado(-1, 99, "movie")
assert "ROLLBACK" in c.sql() and "UPDATE sent_items SET sent_at=%s WHERE item_id=%s" in c.sql()
print("migração/fallbacks OK")

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
