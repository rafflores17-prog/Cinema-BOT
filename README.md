# 🎬 Cinema BOT v8.3 — StreamFlix SaaS Edition

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

## O que há de novo na v8.3

- Cards de filme/série com layout limpo: categoria (LANÇAMENTO, SUGESTÃO DA NOITE, SÉRIE), título em negrito + ano, nota/duração/gêneros, sinopse e hashtags (#Filme #Acao).
- Botões do card: **▶️ Assista no StreamFlix** + **🎞 Trailer** na primeira linha, **📲 Baixar app** na segunda. Pôster em w780.
- Agenda temática nos mesmos horários de antes: 8h = lançamentos (1 filme + 1 série); 20h = sugestão da noite com tema do dia (comédia, ação, terror, romance/drama, família, séries, clássicos).
- Propaganda das 15h e o post do app às 17h no mesmo visual (site + códigos do Downloader + Indique e ganhe).
- Menu do grupo: um card de destaque + títulos em botões, com **Mais ▶️**. O teclado fixo sai do grupo (fica só no privado). Guia em `/comandos` (também `/tutorial` e `/ajuda`).
- Assistente opcional (`/ia`, menção ou resposta ao bot), desligado por padrão. Use um endpoint compatível com OpenAI; o recomendado é o Groq (veja abaixo).

## Postagens automáticas (America/Fortaleza)

- **8h** (11:00 UTC) — 🌅 Lançamentos de hoje: 1 filme em cartaz + 1 série (ou 2 filmes)
- **15h** (18:00 UTC) — 1 post curto do app (site, Downloader, Indique e ganhe)
- **17h** (20:00 UTC) — post diário do app
- **20h** (23:00 UTC) — 🌙 Sugestão da noite (tema do dia, se `THEMED_NIGHTS=1`):
  - seg comédia · ter ação · qua terror · qui romance/drama · sex família/animação · sáb séries · dom clássicos
- **Sexta 18h** (21:00 UTC) — enquete + CTA

Evita repetir o mesmo título do TMDB no chat por 30 dias (tabela `sent_items` já existente + memória). Horários da manhã/noite: `MANHA_HOUR_UTC` e `NOITE_HOUR_UTC`.

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

### Novas (v8.3) — todas opcionais

| Variável | Padrão | Descrição |
|---|---|---|
| `THEMED_NIGHTS` | `1` | Tema da sugestão da noite por dia da semana. `0` = populares variados |
| `MANHA_HOUR_UTC` | `11` | Hora UTC dos lançamentos (11 = 8h America/Fortaleza) |
| `NOITE_HOUR_UTC` | `23` | Hora UTC da sugestão da noite (23 = 20h America/Fortaleza) |
| `MANHA_INCLUIR_SERIE` | `1` | `1` = 1 filme + 1 série de manhã; `0` = 2 filmes |
| `MANHA_HEADER` / `NOITE_HEADER` | (textos padrão) | Cabeçalhos curtos das postagens de 8h e 20h |
| `DIAS_SEM_REPETIR` | `30` | Dias sem repetir o mesmo título no mesmo chat |
| `TMDB_POSTER_SIZE` | `w780` | Tamanho do pôster no TMDB (`w500`, `w780`, `w1280`) |
| `PROPAGANDA_USE_DB` | `0` | `1` = usa os textos de propaganda salvos no painel (senão, os textos novos do app) |
| `AI_ENABLED` | `0` | Liga o assistente (`/ia`, menção ou resposta ao bot, e texto no privado) |
| `AI_BASE_URL` | `https://api.groq.com/openai/v1` | Endpoint compatível com OpenAI `/chat/completions` |
| `AI_API_KEY` | (vazio) | Chave do provedor (não aparece nos logs) |
| `AI_MODEL` | `openai/gpt-oss-20b` | Modelo no provedor (padrão Groq) |
| `AI_RATE_SECONDS` | `20` | Intervalo mínimo entre perguntas do mesmo usuário |
| `AI_DAILY_CAP` | `15` | Máximo de perguntas por usuário por dia (Fortaleza) |
| `AI_MAX_TOKENS` | `350` | Teto de tokens da resposta |

Para ligar a IA no Groq (recomendado, plano gratuito): crie uma chave em https://console.groq.com/keys e no Koyeb defina `AI_ENABLED=1` e `AI_API_KEY` com essa chave. Os outros valores já vêm no padrão. Limites publicados: https://console.groq.com/docs/rate-limits

## 📦 Instalação

```bash
pip install -r requirements.txt
python bot.py
```
