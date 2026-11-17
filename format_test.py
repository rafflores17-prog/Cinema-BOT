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
res = [{"id": 10, "title": "Duna", "original_title": "Dune", "media_type": "movie", "popularity": 90, "vote_count": 9000},
       {"id": 11, "title": "Duna", "original_title": "Dune", "media_type": "movie", "popularity": 10, "vote_count": 900, "release_date": "1984"},
       {"id": 12, "title": "Duna: Parte Dois", "media_type": "movie", "popularity": 80, "vote_count": 5000}]
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
