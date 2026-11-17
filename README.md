# 🎬 Cinema BOT v8.1 — StreamFlix SaaS Edition

Bot de cinema para Telegram (multi-tenant): posts automáticos, tokens de ativação, painel web e divulgação do StreamFlix.

O painel oficial é o [CINEMA-BOT-PAINEL](https://github.com/rafflores17-prog/CINEMA-BOT-PAINEL) em https://cinema-bot-painel.vercel.app — ele fala com a API `GET/POST /admin` deste bot (hospedado no Koyeb).

## O que há de novo na v8.1

- API do painel aceita a senha no header `X-Admin-Pass` ou no corpo JSON (`{"cmd":"...","pass":"..."}`). O query param `?pass=` ainda funciona na transição.
- CORS liberado só para `https://cinema-bot-painel.vercel.app` e localhost.
- Boas-vindas a novos membros nos grupos principais, com site e códigos do Downloader (Indique e ganhe). Anti-flood e apaga a mensagem depois de um tempo (configurável).
- Botão dos cards: **Assista no StreamFlix** (mesmo link de antes).
- Post diário curto do app (padrão 17h em America/Fortaleza).
- Enquete semanal (padrão sexta 18h em America/Fortaleza) com títulos do TMDB.

Os horários dos jobs, como já era no bot, são definidos em **UTC**. America/Fortaleza = UTC−3, então 20:00 UTC = 17:00 no horário de Fortaleza.

## Postagens automáticas (já existentes)

- **8h America/Fortaleza** (11:00 UTC) — filmes em cartaz
- **20h America/Fortaleza** (23:00 UTC) — trending da semana
- Propagandas rotativas às 10h, 15h e 19h America/Fortaleza

## ⚙️ Variáveis de ambiente (Koyeb)

### Obrigatórias / principais

| Variável | Descrição |
|---|---|
| `BOT_TOKEN` ou `TOKEN` | Token do BotFather |
| `TMDB_API_KEY` | Chave da API do TMDB |
| `DATABASE_URL` | PostgreSQL (Neon/Supabase) |
| `PANEL_PASS` | Senha da API `/admin` do painel web |
| `ADMIN_ID` | Seu user_id do Telegram (comandos admin) |
| `SITE_URL` | Site do StreamFlix (padrão: `https://www.streamflixvip.online`) |
| `APP_URL` | Link de download do APK |
| `GRUPO_ID` | ID do grupo/canal principal |
| `CANAL_VIP` | ID do segundo grupo/canal (opcional) |
| `TOPIC_ID` | ID do tópico (0 se não usar) |
| `ADMIN_CONTATO` | Contato nas propagandas (ex.: `@usuario`) |
| `BOT_PUBLIC_URL` | URL pública do bot no Koyeb (webhook Mercado Pago) |
| `MP_ACCESS_TOKEN` | Token do Mercado Pago (opcional) |
| `PORT` | Porta do healthcheck / API (padrão: 8000) |

`GET /` responde `StreamFlix BOT OK`.

### Novas (v8.1) — todas opcionais

| Variável | Padrão | Descrição |
|---|---|---|
| `WELCOME_ENABLED` | `1` (ligado) | Boas-vindas a quem entra no grupo |
| `WELCOME_CHAT_IDS` | (vazio) | IDs extras, separados por vírgula. Sempre inclui `GRUPO_ID` e `CANAL_VIP` |
| `WELCOME_INCLUDE_CLIENTS` | `0` | Se `1`, também dá boas-vindas nos chats dos clientes ativos |
| `WELCOME_DELETE_SECONDS` | `180` | Apaga a mensagem de boas-vindas depois de N segundos. `0` = não apaga |
| `WELCOME_RATE_SECONDS` | `45` | Intervalo mínimo entre boas-vindas no mesmo chat (anti-flood) |
| `BUTTON_ASSISTA` | `1` | Rótulo **Assista no StreamFlix**. `0` = texto antigo do botão |
| `APP_PROMO_ENABLED` | `1` | Post diário curto do app |
| `APP_PROMO_HOUR_UTC` | `20` | Hora UTC do post (20 = 17h em America/Fortaleza). Evita 11:00 e 23:00 UTC |
| `POLL_ENABLED` | `1` | Enquete semanal |
| `POLL_WEEKDAY` | `4` | Dia da semana (0=segunda … 4=sexta) |
| `POLL_HOUR_UTC` | `21` | Hora UTC da enquete (21 = 18h em America/Fortaleza) |
| `POLL_QUESTION` | `🎬 Qual filme você quer ver no fim de semana?` | Pergunta da enquete |
| `DOWNLOADER_CELULAR` | `6085325` | Código Indique e ganhe (celular) |
| `DOWNLOADER_TV` | `3422972` | Código Indique e ganhe (TV) |
| `PANEL_CORS_ORIGINS` | (vazio) | Origens extras de CORS, separadas por vírgula |

Para desligar um recurso: `WELCOME_ENABLED=0`, `APP_PROMO_ENABLED=0`, `POLL_ENABLED=0` ou `BUTTON_ASSISTA=0`.

## 📦 Instalação

```bash
pip install -r requirements.txt
python bot.py
```
