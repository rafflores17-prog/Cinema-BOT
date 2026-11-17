#!/usr/bin/env python3
"""Teste offline: suporte no WhatsApp e troca de links antigos."""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["SUPORTE_URL"] = "https://chat.whatsapp.com/HwROmfEeCgk3IqDfeB5iEm?s=abc123#x"
import bot
W = "https://chat.whatsapp.com/HwROmfEeCgk3IqDfeB5iEm"
assert bot.SUPORTE_URL == W, bot.SUPORTE_URL
assert bot.suporte_html() == f'<a href="{W}">💬 Suporte no WhatsApp</a>'
assert bot.SUPORTE_BOTAO == "💬 Suporte (WhatsApp)"
assert bot.markup_suporte().inline_keyboard[0][0].url == W
t = bot.trocar_links_antigos(
    "Fale: https://t.me/streamflixofc ou t.me/+jPjv75TOACplMmYx ou @streamflixofc ou https://t.me/streamflixvip\n"
    '<a href="https://t.me/streamflixofc">@streamflixofc</a>\n'
    "Grupo: https://t.me/streamflixvipfilmes · site https://www.streamflixvip.online · {x}")
print(t)
assert "streamflixofc" not in t and "jPjv" not in t and "t.me/streamflixvip\n" not in t
assert t.count(W) == 5 and "https://t.me/streamflixvipfilmes" in t and "www.streamflixvip.online" in t
assert "{x}" in t
# ADMIN_CONTATO antigo -> suporte; atual -> mantido
for antigo in ("@streamflixofc", "https://t.me/streamflixofc", "t.me/streamflixofc", ""):
    bot.ADMIN_CONTATO = antigo
    assert bot.contato_html() == bot.suporte_html(), antigo
bot.ADMIN_CONTATO = "@RaffDimitri"
assert bot.contato_html() == "@RaffDimitri"
assert bot.aplicar_contato("Fale com {contato} {suporte} {site} {chave}") == \
    f"Fale com @RaffDimitri {bot.suporte_html()} https://www.streamflixvip.online {{chave}}"
assert bot._aplicar_contato_seguro("{contato} https://t.me/streamflixofc").count(W) == 1
# nenhum texto do bot cita links antigos ou mostra a URL do suporte crua
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.py"), encoding="utf-8").read()
assert "{CANAL_SUPORTE}" not in src and "+ CANAL_SUPORTE" not in src
for txt in [bot.texto_saas("StreamFlixVip_Bot"), bot.texto_tutorial("StreamFlixVip_Bot")]:
    assert W in txt and ">💬 Suporte no WhatsApp</a>" in txt and not re.search(r"(?<!\")" + re.escape(W), txt), txt
kb = bot.markup_start_privado()
assert any(b.url == W and b.text == "💬 Suporte (WhatsApp)" for row in kb.inline_keyboard for b in row)
assert "WhatsApp" in bot.ai_system_prompt()
print("OK: links_test")
