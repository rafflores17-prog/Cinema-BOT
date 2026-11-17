#!/usr/bin/env python3
"""Testes offline (sem token, sem rede) da lista, da busca por texto e do HTML da IA."""
import bot

bot._GENEROS_TMDB.update({28: "Ação", 12: "Aventura", 878: "Ficção científica", 18: "Drama",
                          10765: "Sci-Fi & Fantasy"})
bot._GENEROS_TMDB_TS[0] = 9e12

itens = [
    {"id": 1, "title": "Duna: Parte Dois", "release_date": "2024-03-01", "vote_average": 8.2,
     "vote_count": 5000, "genre_ids": [878, 12], "media_type": "movie"},
    {"id": 2, "name": "The Last of Us", "first_air_date": "2023-01-15", "vote_average": 8.6,
     "vote_count": 4000, "genre_ids": [18, 10765], "media_type": "tv"},
    {"id": 3, "title": "Filme <Raro> & Cia", "release_date": "", "vote_average": 0, "genre_ids": []},
]
txt = bot.texto_vitrine("🎬 Em cartaz agora", itens, 1, total=18)
print(txt, "\n---")
assert "&lt;Raro&gt; &amp; Cia" in txt and "⭐ 8,2" in txt and "Ficção científica" in txt
print(bot.rotulo_item(itens[1], numero=2))

# classificação texto
for t, grupo, esperado in [
    ("Duna", True, True), ("The Last of Us", True, True), ("bom dia", True, False),
    ("kkkkk", True, False), ("como instalar na TV?", False, False), ("qual o preço", False, False),
    ("indica um terror", False, False), ("https://x.com", True, False), ("oi", False, False),
    ("vingadores ultimato", True, True), ("um filme de comedia", False, False),
    ("alguém sabe se vai ter jogo hoje à noite no app de vocês", True, False),
]:
    r = bot.parece_titulo(t, grupo=grupo)
    print(f"{t!r:60} grupo={grupo} -> {r}")
    assert r == esperado, t

# escolha de resultado
res = [{"id": 10, "title": "Duna", "original_title": "Dune", "media_type": "movie", "popularity": 90, "vote_count": 9000, "poster_path": "/a.jpg"},
       {"id": 11, "title": "Duna", "original_title": "Dune", "media_type": "movie", "popularity": 10, "vote_count": 900, "release_date": "1984", "poster_path": "/b.jpg"},
       {"id": 12, "title": "Duna: Parte Dois", "media_type": "movie", "popularity": 80, "vote_count": 5000, "poster_path": "/c.jpg"}]
assert bot.escolher_resultado("duna", res) == ("card", res[0])
assert bot.escolher_resultado("dun", res)[0] == "lista"
assert [r["id"] for r in bot.match_relevante("duna", res)] == [10, 11, 12]
assert bot.match_relevante("bolo de cenoura", res) == []

# IA markdown -> HTML
resp = """### **Filmes de terror para hoje** 🎃
Aqui vão algumas ideias:

* **Invocação do Mal** (2013) — clássico moderno & assustador
- **Hereditário** (2018) — tenso <de verdade>
1. Abra o `Downloader` e digite 3422972
| Filme | Nota |
|---|---|
| Fale Comigo | 7,1 |
Mais em [site](https://www.streamflixvip.online)
TITULOS: Invocação do Mal (2013); Hereditário (2018); Fale Comigo
"""
corpo, titulos = bot.ai_separar_titulos(resp)
print(titulos)
assert titulos == [("Invocação do Mal", "2013"), ("Hereditário", "2018"), ("Fale Comigo", "")]
h = bot.md_para_html(corpo)
print(h, "\n---")
assert "<b>Filmes de terror para hoje 🎃</b>" in h
assert "• <b>Invocação do Mal</b> (2013) — clássico moderno &amp; assustador" in h
assert "&lt;de verdade&gt;" in h and "<code>Downloader</code>" in h
assert "|" not in h and "###" not in h and "**" not in h
assert '<a href="https://www.streamflixvip.online">site</a>' in h
print(bot.md_para_texto(corpo))
long = bot.md_para_html("**Título**\n" + ("palavra " * 400))
assert len(long) < 1300 and long.endswith("…")
print("OK: todos os testes passaram")

# ---- botões dos títulos citados pela IA (TMDB simulado, pt-BR e en-US) ----
FAKE = {
    "pt-BR": [
        {"id": 493922, "media_type": "movie", "title": "Hereditário", "original_title": "Hereditary", "release_date": "2018-06-07", "vote_count": 9000},
        {"id": 310131, "media_type": "movie", "title": "A Bruxa", "original_title": "The Witch", "release_date": "2015-01-27", "vote_count": 7000},
        {"id": 346364, "media_type": "movie", "title": "It: A Coisa", "original_title": "It", "release_date": "2017-09-06", "vote_count": 20000},
        {"id": 474350, "media_type": "movie", "title": "It: Capítulo Dois", "original_title": "It Chapter Two", "release_date": "2019-09-04", "vote_count": 9000},
        {"id": 19614, "media_type": "tv", "name": "It: Uma Obra-Prima do Medo", "original_name": "It", "first_air_date": "1990-11-18", "vote_count": 1500},
        {"id": 496243, "media_type": "movie", "title": "Parasita", "original_title": "기생충", "release_date": "2019-05-30", "vote_count": 18000},
    ],
}
FAKE["en-US"] = [dict(r, title={"Hereditário": "Hereditary", "A Bruxa": "The Witch", "It: A Coisa": "It",
                                "It: Capítulo Dois": "It Chapter Two", "Parasita": "Parasite"}.get(r.get("title"), r.get("title")))
                 for r in FAKE["pt-BR"]]
def fake_tmdb(ep, params=None):
    q = bot.normalizar_busca(params["query"])
    out = []
    for r in FAKE[params.get("language", "pt-BR")]:
        nomes = {bot.normalizar_busca(r.get(k) or "") for k in ("title", "original_title", "name", "original_name")}
        if any(q and (q in n or n in q) for n in nomes if n):
            out.append(r)
    return {"results": out}
bot.tmdb = fake_tmdb
casos = [("Hereditary", "2018", 493922), ("Hereditário", "", 493922), ("The Witch", "2015", 310131),
         ("A Bruxa", "2015", 310131), ("It", "2017", 346364), ("It: A Coisa", "2017", 346364),
         ("It Chapter Two", "2019", 474350), ("Parasite", "2019", 496243)]
for nome, ano, esperado in casos:
    achado = bot._match_titulo_tmdb(nome, ano)
    print(nome, ano, "->", achado)
    assert achado and achado[1] == esperado, nome
mk = bot.ai_botoes_titulos([("Hereditary", "2018"), ("The Witch", "2015"), ("It", "2017"), ("Parasite", "2019"), ("Duna", "2021")])
print([b[0].text for b in mk.inline_keyboard])
assert len(mk.inline_keyboard) == 4
print("OK: botões da IA")

# ---- gêneros digitados, match forte e frases de botão ----
assert bot.detectar_genero("terror") == ("👻 Terror", 27, False)
assert bot.detectar_genero("Filmes de Ação") == ("🔥 Ação", 28, False)
assert bot.detectar_genero("séries de comédia") == ("🤡 Comédia", 35, True)
assert bot.detectar_genero("um filme de terror")[1] == 27
assert bot.detectar_genero("ficção científica")[1] == 878
assert bot.detectar_genero("Duna") is None and bot.detectar_genero("quero um terror bem assustador") is None
lixo = [{"id": 5, "name": "Terror", "media_type": "tv", "popularity": 0.6, "vote_count": 0}]
assert bot.escolher_resultado("terror", lixo)[0] == "lista"
bom = [{"id": 6, "title": "Duna", "media_type": "movie", "poster_path": "/x.jpg", "popularity": 50, "vote_count": 9000}]
assert bot.escolher_resultado("duna", bom + lixo)[0] == "card"
t = "**Como instalar na TV**\n1. Abra o Downloader\n2. Digite 3422972\nToque no botão abaixo para ver o card."
limpo = bot.limpar_frases_botao(t)
print(limpo)
assert "botão" not in limpo and "3422972" in limpo
assert bot.limpar_frases_botao("Pronto! Clique no card abaixo para ver mais. Bom filme!") == "Pronto! Bom filme!"
print("OK: gêneros/match/frases")

# ---- variantes de busca e curadoria ----
v = bot.variantes_busca("Outra mamãe")
print(v)
assert v[0] == "Outra mamãe" and "outra mae" in v and "a outra mae" in v
docs = [{"id": i, "name": f"Doc {i}", "genre_ids": [99], "vote_count": 5000, "poster_path": "/d.jpg"} for i in range(1, 4)]
pop = [{"id": 10 + i, "title": f"Filme {i}", "genre_ids": [28], "vote_count": 300 + i, "poster_path": "/p.jpg"} for i in range(5)]
fracos = [{"id": 50, "title": "Obscuro", "genre_ids": [28], "vote_count": 3, "poster_path": "/o.jpg"}]
cur = bot.curar_itens(docs + pop + fracos, min_votos=200)
assert {i["id"] for i in cur} == {10, 11, 12, 13, 14}
assert {i["id"] for i in bot.curar_itens(docs, permitir_doc=True)} == {1, 2, 3}
assert bot.curar_itens(fracos + docs, min_votos=200)[0]["id"] == 50   # afrouxa, mas sem doc
print("OK: variantes/curadoria")
