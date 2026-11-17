# 🎬 Cinema BOT v8.2 — StreamFlix SaaS Edition

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

## O que há de novo na v8.2

- Menu de comandos em português, com escopos diferentes no privado, nos grupos e no admin (configurado na inicialização).
- `/start` no privado foca no app StreamFlix (baixar, lançamentos, Indique e ganhe, suporte). O texto de aluguel do bot no canal ficou em `/start saas`.
- Deep links: `t.me/StreamFlixVip_Bot?start=indique`, `?start=baixar`, `?start=lancamentos`, `?start=ref_SEUCODIGO`.
- Busca liberada no privado (`PUBLIC_SEARCH`, ligado por padrão), com limite de frequência.
- `/filme` e `/serie` mostram até 5 resultados para o usuário escolher, em vez de enviar só o primeiro.
- Modo inline (`@StreamFlixVip_Bot nome do filme`) — precisa estar ligado no BotFather.
- `/indique` e botão "Assista no StreamFlix" também no Top 10.
- Menos volume no grupo: a mensagem extra de trailer sai do padrão (o botão no card continua); a propaganda rotativa passa a 1x ao dia (15h America/Fortaleza). A divulgação do app e a enquete vão só para o grupo/canal oficiais, não para clientes SaaS.

O bot **não** altera nome, foto ou descrição automaticamente. A descrição só muda se `SET_BOT_PROFILE=1` (e o texto tiver sido aprovado).

## Postagens automáticas

- **8h America/Fortaleza** (11:00 UTC) — filmes em cartaz (2 cards)
- **15h America/Fortaleza** (18:00 UTC) — 1 propaganda rotativa (antes era 3x ao dia; para voltar: `PROPAGANDA_HOURS_UTC=13,18,22`)
- **17h America/Fortaleza** (20:00 UTC) — post curto do app
- **20h America/Fortaleza** (23:00 UTC) — trending da semana (2 cards)
- **Sexta 18h America/Fortaleza** (21:00 UTC) — enquete + CTA

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

### Novas (v8.2) — todas opcionais

| Variável | Padrão | Descrição |
|---|---|---|
| `PUBLIC_SEARCH` | `1` | Libera `/filme`, `/serie`, `/ator` e `/top10` no privado, mesmo sem plano SaaS |
| `SEND_TRAILER_MESSAGE` | `0` | Se `1`, volta a enviar a 2ª mensagem de trailer (o card já tem o botão) |
| `APP_PROMO_INCLUDE_CLIENTS` | `0` | Se `1`, o post diário do app também vai para canais de clientes SaaS |
| `POLL_INCLUDE_CLIENTS` | `0` | Se `1`, a enquete semanal também vai para clientes SaaS |
| `COMMAND_RATE_SECONDS` | `8` | Intervalo mínimo entre buscas no privado. `0` desliga |
| `GROUP_SEARCH_RATE_SECONDS` | `30` | Intervalo mínimo entre buscas no mesmo usuário, nos grupos |
| `PROPAGANDA_HOURS_UTC` | `18` | Horários UTC da propaganda, separados por vírgula. Antes: `13,18,22` |
| `INLINE_MODE` | `1` | Responde a buscas inline (`@bot nome`). O modo inline precisa estar ligado no BotFather |
| `SET_BOT_PROFILE` | `0` | Se `1`, aplica descrição/descrição curta na inicialização (não mexe em nome nem foto) |
| `BOT_SHORT_DESCRIPTION` | (texto padrão) | Descrição curta (até 120 caracteres), só usada se `SET_BOT_PROFILE=1` |
| `BOT_DESCRIPTION` | (texto padrão) | Texto de "O que este bot faz?" (até 512 caracteres), só se `SET_BOT_PROFILE=1` |

## 📦 Instalação

```bash
pip install -r requirements.txt
python bot.py
```
