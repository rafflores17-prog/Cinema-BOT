#!/usr/bin/env python3
"""Testes offline da busca por texto (TMDB simulado): exato > variante, pessoas, rivais."""
import sys, os, asyncio, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timedelta
import bot

hoje = datetime.utcnow()
recente = (hoje - timedelta(days=40)).strftime("%Y-%m-%d")
DB = {
    "outra mamae": [
        {"id": 1, "media_type": "movie", "title": "Outra Mamãe", "original_title": "Other Mommy",
         "release_date": recente, "poster_path": "/om.jpg", "vote_count": 7, "popularity": 4.0, "genre_ids": [27]},
        {"id": 2, "media_type": "movie", "title": "Mamãe Zumbi", "original_title": "Zombie Mom",
         "release_date": "2019-01-01", "poster_path": "/z.jpg", "vote_count": 30, "popularity": 2.0},
    ],
    "outra mae": [
        {"id": 3, "media_type": "movie", "title": "A Outra Mãe", "original_title": "The Other Mother",
         "release_date": "2017-05-01", "poster_path": "/a.jpg", "vote_count": 40, "popularity": 6.0},
    ],
    "pedro pascal": [
        {"id": 50, "media_type": "person", "name": "Pedro Pascal", "popularity": 80, "known_for_department": "Acting",
         "profile_path": "/pp.jpg", "known_for": [{"title": "The Mandalorian"}, {"name": "The Last of Us"}]},
    ],
    "duna": [
        {"id": 10, "media_type": "movie", "title": "Duna", "original_title": "Dune", "poster_path": "/d.jpg",
         "release_date": "2021-09-15", "vote_count": 9000, "popularity": 90},
        {"id": 11, "media_type": "movie", "title": "Duna", "original_title": "Dune", "poster_path": "/d2.jpg",
         "release_date": "1984-12-14", "vote_count": 900, "popularity": 10},
        {"id": 12, "media_type": "movie", "title": "Duna: Parte Dois", "original_title": "Dune: Part Two",
         "poster_path": "/d3.jpg", "release_date": "2024-03-01", "vote_count": 5000, "popularity": 85},
    ],
    "matrix": [
        {"id": 603, "media_type": "movie", "title": "Matrix", "original_title": "The Matrix", "poster_path": "/m.jpg",
         "release_date": "1999-03-31", "vote_count": 25000, "popularity": 60},
        {"id": 604, "media_type": "movie", "title": "Matrix Reloaded", "original_title": "The Matrix Reloaded",
         "poster_path": "/m2.jpg", "release_date": "2003-05-15", "vote_count": 10000, "popularity": 20},
    ],
}
CREDITS = {"cast": [
    {"id": 82856, "media_type": "tv", "name": "The Mandalorian", "poster_path": "/x.jpg", "popularity": 90, "episode_count": 24, "character": "Din Djarin"},
    {"id": 100088, "media_type": "tv", "name": "The Last of Us", "poster_path": "/y.jpg", "popularity": 120, "episode_count": 16, "character": "Joel"},
    {"id": 7, "media_type": "tv", "name": "Talk Show", "poster_path": "/t.jpg", "popularity": 500, "genre_ids": [10767], "character": "Self"},
    {"id": 8, "media_type": "movie", "title": "Bastidores", "poster_path": "/b.jpg", "popularity": 300, "genre_ids": [99], "character": "Himself"},
    {"id": 9, "media_type": "tv", "name": "Série X", "poster_path": "/s.jpg", "popularity": 200, "episode_count": 1, "character": "Guest"},
    {"id": 10, "media_type": "movie", "title": "Gladiador II", "poster_path": "/g.jpg", "popularity": 70, "character": "Marcus"},
]}
JACKIE = {"id": 18897, "media_type": "person", "name": "Jackie Chan", "popularity": 45, "known_for_department": "Acting",
          "profile_path": "/jc.jpg", "known_for": [{"title": "A Hora do Rush"}]}
JACK_RUIM = {"id": 777, "media_type": "person", "name": "Jack Chandler", "popularity": 0.5, "known_for": [{"title": "X"}]}
SCARLETT = {"id": 1245, "media_type": "person", "name": "Scarlett Johansson", "popularity": 60, "known_for_department": "Acting",
            "profile_path": "/sj.jpg", "known_for": [{"title": "Viúva Negra"}]}
DB["jackie chan"] = [JACKIE]
# espelha a resposta real do TMDB para "Jack Chan" (títulos fracos, sem o Jackie no multi)
DB["jack chan"] = [
    {"id": 901, "media_type": "tv", "name": "Gentleman Jack Changed My Life", "original_name": "Gentleman Jack Changed My Life",
     "poster_path": "/g.jpg", "overview": "doc", "vote_count": 2, "popularity": 1.1, "first_air_date": "2020-01-01"},
    {"id": 902, "media_type": "movie", "title": "Jack Bensinger", "original_title": "Jack Bensinger",
     "poster_path": "/jb.jpg", "vote_count": 1, "popularity": 0.6},
    {"id": 903, "media_type": "tv", "name": "ブラック・ジャック", "original_name": "ブラック・ジャック",
     "poster_path": "/bj.jpg", "vote_count": 30, "popularity": 6},
    {"id": 904, "media_type": "movie", "title": "A Última Chance", "original_title": "Last Chance",
     "poster_path": "/uc.jpg", "vote_count": 80, "popularity": 7},
    {"id": 905, "media_type": "movie", "title": "Emperor of Hemp: The Jack Herer Story", "original_title": "Emperor of Hemp",
     "poster_path": "/eh.jpg", "vote_count": 10, "popularity": 1.5},
    JACK_RUIM,
]
DB["lixo total"] = DB["jack chan"][:5]
PESSOAS = {"jack chan": [JACK_RUIM, JACKIE], "scarlet johanson": [SCARLETT], "scarlet johansson": [SCARLETT]}
calls = []
def fake_tmdb(ep, params=None):
    calls.append((ep, (params or {}).get("query")))
    if ep.startswith("search/multi"):
        q = bot.normalizar_busca(params["query"])
        if params.get("page", 1) > 1:
            return {"results": [], "total_pages": 1}
        return {"results": DB.get(q, []), "total_pages": 1}
    if ep == "search/person":
        return {"results": PESSOAS.get(bot.normalizar_busca(params["query"]), [])}
    if ep.endswith("/combined_credits"):
        return CREDITS
    return {}
bot.tmdb = fake_tmdb

p = bot.planejar_busca("Outra mamãe", grupo=True)
print("grupo Outra mamãe ->", p[0], p[1].get("title"))
assert p[0] == "card" and p[1]["id"] == 1
assert not any(q and bot.normalizar_busca(q) == "outra mae" for _, q in calls), "não deve tentar variante antes"
p = bot.planejar_busca("Outra mamãe")
assert p[0] == "card" and p[1]["id"] == 1
p = bot.planejar_busca("Outra mãe", grupo=True)
print("grupo Outra mãe ->", p[0], p[1]["title"] if p[0] == "card" else p)
assert p[0] == "card" and p[1]["id"] == 3
p = bot.planejar_busca("Duna")
print("Duna ->", p[0], [i["title"] for i in p[1]] if p[0] == "lista" else p[1]["title"])
assert p[0] == "lista" and p[1][0]["id"] == 10      # exato + rival popular -> lista
p = bot.planejar_busca("Matrix")
assert p[0] == "card" and p[1]["id"] == 603         # rival bem menos popular -> card
p = bot.planejar_busca("Pedro Pascal", grupo=True)
assert p[0] == "pessoa" and p[1]["id"] == 50
obras = bot.carregar_obras_pessoa(50, "Acting")
print("obras:", [o.get("name") or o.get("title") for o in obras])
assert [o["id"] for o in obras] == [100088, 82856, 10]
assert bot.planejar_busca("xyzzy qwerty")[0] is None
for q, esperado in [("Jack Chan", 18897), ("Jackie Chan", 18897), ("jackie chan", 18897), ("Pedro Pascal", 50),
                    ("Scarlet Johansson", 1245), ("Scarlet Johanson", 1245)]:
    for g in (False, True):
        p = bot.planejar_busca(q, grupo=g)
        print(q, "grupo" if g else "privado", "->", p[0], p[1].get("name") if p[0] == "pessoa" else "")
        assert p[0] == "pessoa" and p[1]["id"] == esperado, (q, g)
assert bot.planejar_busca("lixo total")[0] is None            # títulos que não batem não viram lista
assert bot.planejar_busca("lixo total", grupo=True)[0] is None
assert not bot.titulo_relevante("jack chan", DB["jack chan"][0])   # "chan" não vira "changed"
assert bot.titulo_relevante("duna", DB["duna"][2]) and bot.titulo_relevante("matrx", DB["matrix"][0])
assert bot.nome_pessoa_bate("jack chan", "jackie chan") and bot.nome_pessoa_bate("scarlet johanson", "scarlett johansson")
assert not bot.nome_pessoa_bate("jack", "jackie chan") and not bot.nome_pessoa_bate("pedro", "pedro pascal")
assert bot.nome_pessoa_bate("zendya", "zendaya") and not bot.nome_pessoa_bate("bom dia", "bomani diaz")
assert not bot.nome_pessoa_bate("ana", "anabelle")

sent = []
class FakeBot:
    async def send_message(self, chat_id, text, **kw):
        sent.append(("msg", text, kw.get("reply_markup"))); return types.SimpleNamespace(message_id=1)
    async def send_photo(self, chat_id, photo, caption=None, **kw):
        sent.append(("photo", caption, photo)); return types.SimpleNamespace(message_id=1)
bot.get_topic_id = lambda c: 0
bot.dica_ocasional = lambda: None
ctx = types.SimpleNamespace(bot=FakeBot())
asyncio.run(bot.enviar_pessoa(ctx, 5, DB["pedro pascal"][0]))
print(sent[0][1]); print(sent[1][1][:160])
assert sent[0][0] == "photo" and "h632" in sent[0][2] and "Pedro Pascal" in sent[0][1]
assert "The Last of Us" in sent[1][1] and "Talk Show" not in sent[1][1]
assert sent[1][2].inline_keyboard[0][0].callback_data == "ver:tv:100088"
print("OK: search_test")
