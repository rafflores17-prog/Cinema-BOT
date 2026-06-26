# 🎬 Cinema BOT v7.0 — StreamFlix Edition

## ✅ O que mudou da v6 para a v7

### 🔗 Bug do Deep Link — CORRIGIDO
O bot agora abre direto no filme dentro do app StreamFlix.

**Antes (errado):**
```
https://streamflix.app/#detail-12345-movie
```

**Agora (correto):**
```
https://streamflix.app/#/title/12345/movie
```

O app usa `hashchange` com rota `#/title/{id}/{type}` —
exatamente isso que a função `link_streamflix()` agora gera.

---

### 📋 Mais informações no card do filme/série
Antes mostrava só título, nota e sinopse.

Agora mostra:
- ⭐ Nota detalhada com quantidade de votos
- 🎭 Gêneros
- ⏱ Duração (filmes) ou 📺 Temporadas + episódios (séries)
- 🟢 Status da série (em exibição, encerrada, cancelada...)
- 🌟 Elenco principal (top 5 atores)
- 🎬 Diretor (filmes) ou ✍️ Criadores (séries)
- Título original quando diferente

---

### 🆕 Novos comandos
- `/ator Nome` — lista filmes de um ator/atriz
- `/top10` — envia o Top 10 da semana com links diretos

---

### ⏰ Postagens automáticas
- **8h BRT** — filmes em cartaz
- **20h BRT** — trending da semana

---

## ⚙️ Variáveis de ambiente (Koyeb)

| Variável | Descrição |
|---|---|
| `BOT_TOKEN` | Token do BotFather |
| `TMDB_API_KEY` | Chave da API do TMDB |
| `DATABASE_URL` | PostgreSQL (Neon/Supabase) |
| `SITE_URL` | URL do StreamFlix (ex: `https://streamflix-red.zeabur.app`) |
| `APP_URL` | Link de download do app |
| `GRUPO_ID` | ID do grupo/canal Telegram |
| `TOPIC_ID` | ID do tópico (0 se não usar) |
| `PORT` | Porta do healthcheck (padrão: 8000) |

---

## 📦 Instalação

```bash
pip install -r requirements.txt
python bot.py
```
