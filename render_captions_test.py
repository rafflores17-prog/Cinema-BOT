#!/usr/bin/env python3
"""Render 2 sample captions from mocked TMDB payloads. No network, no secrets."""
import sys

import bot

MOVIE = {
    "id": 693134,
    "title": "Duna: Parte Dois",
    "original_title": "Dune: Part Two",
    "release_date": "2024-03-01",
    "vote_average": 8.4,
    "runtime": 166,
    "overview": (
        "Paul Atreides se une a Chani e aos Fremen enquanto busca vingança contra os "
        "conspiradores que destruíram sua família. Enfrentando uma escolha entre o amor "
        "de sua vida e o destino do universo, ele precisa evitar um futuro terrível que "
        "só ele consegue prever. A jornada atravessa o deserto de Arrakis e testa até "
        "onde ele está disposto a ir para proteger os seus."
    ),
    "genres": [{"id": 878, "name": "Ficção científica"}, {"id": 12, "name": "Aventura"}],
}

SERIES = {
    "id": 100088,
    "name": "The Last of Us",
    "original_name": "The Last of Us",
    "first_air_date": "2023-01-15",
    "vote_average": 8.6,
    "number_of_seasons": 2,
    "number_of_episodes": 16,
    "overview": (
        "Joel, um sobrevivente endurecido, e Ellie, uma adolescente de 14 anos, precisam "
        "atravessar os Estados Unidos destruídos por uma pandemia. O que começa como um "
        "trabalho se transforma em um vínculo profundo, enquanto os dois enfrentam "
        "infectados e sobreviventes em um mundo em ruínas."
    ),
    "genres": [{"id": 18, "name": "Drama"}, {"id": 10765, "name": "Ficção científica & Fantasia"}],
}

def main():
    cap1 = bot.build_caption(MOVIE, is_tv=False, categoria="🎬 LANÇAMENTO")
    cap2 = bot.build_caption(SERIES, is_tv=True, categoria="📺 SÉRIE")
    print("=" * 40)
    print("SAMPLE 1 — filme (LANÇAMENTO)")
    print("=" * 40)
    print(cap1)
    print()
    print("=" * 40)
    print("SAMPLE 2 — série")
    print("=" * 40)
    print(cap2)
    print()
    assert len(cap1) <= 1024, len(cap1)
    assert len(cap2) <= 1024, len(cap2)
    assert "#" in cap1 and "Acao" not in cap1  # Ação -> Acao in hashtag, title may vary
    assert "#Filme" in cap1 and "#Serie" in cap2
    assert "#FiccaoCientifica" in cap1 or "#Ficcaocientifica" in cap1
    # sentence-boundary trim
    longo = "Primeira frase completa. Segunda também acaba aqui. " + ("palavra " * 80)
    cortado = bot.cortar_sinopse(longo, 300)
    assert cortado.endswith(".") or cortado.endswith("…")
    promo = bot.texto_promo_app()
    props = bot.textos_propaganda_app()
    assert "6085325" in promo and "3422972" in promo
    assert all("6085325" in t for t in props)
    print(f"OK — caption1={len(cap1)} chars, caption2={len(cap2)} chars (limite 1024)")

if __name__ == "__main__":
    main()
