#!/usr/bin/env python3
"""Teste offline dos handlers (Telegram/TMDB/banco simulados). Rodar com Python 3.11."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asyncio, types, bot
from unittest.mock import AsyncMock, MagicMock
sent=[]
class FakeBot:
    async def send_message(self, chat_id, text, **kw): sent.append(("msg",chat_id,text,kw.get("reply_markup"))); return types.SimpleNamespace(message_id=1)
    async def send_photo(self, chat_id, photo, caption=None, **kw):
        if getattr(self,"photo_fail",False):
            from telegram.error import TimedOut; raise TimedOut()
        sent.append(("photo",chat_id,caption,kw.get("reply_markup"))); return types.SimpleNamespace(message_id=1)
    async def send_chat_action(self,*a,**k): pass
bot.get_topic_id=lambda c:0; bot.get_modo=lambda c:"completo"; bot.get_site_url=lambda c:None
bot.marcar_enviado=lambda *a:None; bot.ids_enviados=lambda *a,**k:set(); bot.cliente_ativo=lambda c:False
bot.GRUPO_ID=-100; bot.dica_ocasional=lambda:None
RES=[{"id":10,"title":"Duna","original_title":"Dune","media_type":"movie","popularity":90,"vote_count":9000,"poster_path":"/a.jpg","release_date":"2021-09-15","vote_average":7.8,"genre_ids":[]},
     {"id":11,"title":"Duna","original_title":"Dune","media_type":"movie","popularity":10,"vote_count":900,"release_date":"1984-12-14","genre_ids":[]},
     {"id":12,"title":"Duna: Parte Dois","media_type":"movie","popularity":80,"vote_count":5000,"genre_ids":[]},
     {"id":99,"name":"Fulano","media_type":"person"}]
def fake_tmdb(ep, params=None):
    if ep.startswith("search/multi"):
        q=params["query"].lower()
        return {"results":[r for r in RES if q in (r.get("title") or r.get("name","")).lower()]}
    if ep.startswith("genre/"): return {"genres":[]}
    if ep.startswith("movie/") : return {"id":10,"title":"Duna","release_date":"2021","overview":"x","genres":[],"poster_path":"/p.jpg","videos":{"results":[]}}
    return {"results":RES}
bot.tmdb=fake_tmdb
def mkupdate(text, chat_type, cid, reply=None, sender_chat=None, user_is_bot=False):
    msg=MagicMock(); msg.text=text; msg.caption=None; msg.reply_to_message=reply; msg.sender_chat=sender_chat; msg.is_automatic_forward=False; msg.via_bot=None; msg.forward_origin=None
    msg.reply_text=AsyncMock()
    u=MagicMock(); u.message=msg; u.effective_message=msg
    u.effective_chat=types.SimpleNamespace(id=cid,type=chat_type)
    u.effective_user=types.SimpleNamespace(id=1087968824 if user_is_bot else 7,first_name="A",is_bot=user_is_bot)
    return u
ctx=MagicMock(); ctx.bot=FakeBot(); ctx.user_data={}
async def main():
    bot.AI_ENABLED=False
    await bot.handle_text(mkupdate("duna","private",5),ctx); print("private 'duna':",[(s[0],s[2][:40]) for s in sent]); sent.clear()
    bot._rate_bucket.clear()
    await bot.handle_text(mkupdate("dun","private",5),ctx); print("private 'dun':",[(s[0],s[2][:60]) for s in sent], len(sent[-1][3].inline_keyboard)); sent.clear()
    bot._rate_bucket.clear()
    await bot.handle_text(mkupdate("bom dia","supergroup",-100),ctx); print("group 'bom dia':",sent); 
    await bot.handle_text(mkupdate("Duna","supergroup",-100),ctx); print("group 'Duna':",[(s[0],s[2][:30]) for s in sent]); sent.clear()
    await bot.handle_text(mkupdate("Duna","supergroup",-100),ctx); print("group repeat (rate):",sent)
    bot._rate_bucket.clear()
    await bot.handle_text(mkupdate("xyzabc","supergroup",-100),ctx); print("group no result:",sent)
    bot._rate_bucket.clear()
    await bot.handle_text(mkupdate("Duna","supergroup",-555),ctx); print("other group no access:",sent)
    bot._rate_bucket.clear(); sent.clear()
    await bot.enviar_vitrine(ctx,5,RES,titulo="🌟 Populares"); print([ (s[0], (s[2] or "")[:200]) for s in sent])
asyncio.run(main())
async def ai():
    bot.AI_ENABLED=True; bot.AI_API_KEY="x"; bot._rate_bucket.clear()
    bot.ai_perguntar=lambda q: "**🎃 Terror pra hoje**\n- **Duna** (2021) — épico\nTITULOS: Duna (2021)"
    u=mkupdate("qual filme de terror vale a pena?","private",5)
    await bot.handle_text(u,ctx)
    a,k=u.message.reply_text.call_args
    print(a[0]); print(k["parse_mode"], k["reply_markup"].inline_keyboard)
asyncio.run(ai())
async def gen():
    bot.AI_ENABLED=False; bot._rate_bucket.clear(); sent.clear()
    await bot.handle_text(mkupdate("terror","private",5),ctx)
    print("terror:", [(s[0], (s[2] or "")[:50]) for s in sent]); sent.clear(); bot._rate_bucket.clear()
    await bot.handle_text(mkupdate("séries de comédia","supergroup",-100),ctx)
    print("grupo séries de comédia:", [(s[0], (s[2] or "")[:50]) for s in sent])
asyncio.run(gen())

import threading
async def cb():
    main_t=threading.get_ident(); threads=[]
    orig=bot.tmdb
    def spy(ep,params=None):
        threads.append(threading.get_ident()); return orig(ep,params)
    bot.tmdb=spy
    bot._rate_bucket.clear(); sent.clear()
    ctx.bot.photo_fail=True
    q=MagicMock(); q.data="ver:movie:10"; q.answer=AsyncMock(side_effect=Exception("Query is too old"))
    u=MagicMock(); u.callback_query=q; u.effective_chat=types.SimpleNamespace(id=5,type="private"); u.effective_user=types.SimpleNamespace(id=9)
    await bot.callback_handler(u,ctx)
    print("callback com foto TimedOut + answer falhando:", [(s[0], (s[2] or "")[:30]) for s in sent])
    assert sent and sent[0][0]=="msg"
    assert threads and main_t not in threads, "tmdb rodou no event loop"
    sent.clear(); await bot.callback_handler(u,ctx)
    print("2º toque imediato:", q.answer.call_args)
    ctx.bot.photo_fail=False
asyncio.run(cb())

async def anon():
    bot.AI_ENABLED=False; bot._rate_bucket.clear(); sent.clear()
    await bot.handle_text(mkupdate("Duna","supergroup",-100,sender_chat=types.SimpleNamespace(id=-100),user_is_bot=True),ctx)
    print("anônimo do grupo:", [(s[0], (s[2] or "")[:20]) for s in sent]); assert sent
    sent.clear(); bot._rate_bucket.clear()
    await bot.handle_text(mkupdate("Duna","supergroup",-100,sender_chat=types.SimpleNamespace(id=-200),user_is_bot=True),ctx)
    print("outro canal:", sent); assert not sent
asyncio.run(anon())
async def adm():
    bot.AI_ENABLED=False; bot._rate_bucket.clear(); sent.clear()
    anon=lambda: mkupdate("Duna","supergroup",-100,sender_chat=types.SimpleNamespace(id=-100),user_is_bot=True)
    await bot.handle_text(anon(),ctx); n1=len(sent)
    bot._rate_bucket[(-100,"txt_adm")]-=9   # passou o limite de 8s do grupo
    await bot.handle_text(anon(),ctx)
    print("anônimo 2x em 9s:", n1, len(sent)); assert len(sent) > n1 > 0
    sent.clear(); bot._rate_bucket.clear()
    await bot.handle_text(mkupdate("Duna","supergroup",-100),ctx); n1=len(sent)
    bot._rate_bucket[(-100,"txt_grupo")]-=21; bot._rate_bucket[(7,"txt")]-=9
    await bot.handle_text(mkupdate("Duna","supergroup",-100),ctx)
    print("usuário comum 2x em 9s:", n1, len(sent)); assert len(sent) == n1
asyncio.run(adm())
