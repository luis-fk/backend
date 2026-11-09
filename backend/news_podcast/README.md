# news_podcast · Resumo das 7

Todo dia chega no Telegram uma mensagem de voz com dois apresentadores (Bia e Léo)
contando o que aconteceu nas 24 horas anteriores, a partir dos feeds do `feeds.opml`. Ela
chega perto das 7h e, no padrão, tem de 12 a 18 minutos (de 8 a 12 em 1,5x). Duração,
velocidade, modelos, preços e prompts mudam no admin do Django (veja *Configurações*). O
episódio é só essa mensagem de voz: o custo e o resultado de cada execução ficam no
histórico do admin, e as fontes usadas, no log da execução no Railway.

O app tem banco próprio, o `news_podcast_db` (`NEWS_PODCAST_DATABASE_URL`), com as
configurações e o histórico. O resto é um management command.

## Como funciona

| Etapa | Arquivo | O que acontece |
|---|---|---|
| Feeds | `api/episode/feeds.py` | Lê o OPML exportado do Feeder, baixa os 9 feeds em paralelo e mantém só o que saiu entre 6h de ontem e 6h de hoje. |
| Seleção | `service.py` + prompt de seleção | O modelo de texto recebe todas as manchetes, junta as que falam do mesmo fato, aplica as regras editoriais e escolhe uma história para cada minuto e meio de episódio (de 8 a 12 no padrão), com o tempo de cada uma. |
| Leitura | `api/episode/articles.py` | Para cada história, lê o texto completo de até 3 veículos (o ICL vem primeiro). Os demais veículos que deram a notícia entram como manchete. Todos os feeds são de sites sem paywall. |
| Roteiro | `service.py` + prompt do roteiro | O modelo de texto escreve o diálogo com 170 palavras por minuto de episódio, vezes a velocidade (de 2.040 a 3.060 palavras no padrão), abrindo com uma escalada de 3 a 5 manchetes curtas, como nos telejornais. Se vier curto demais, pede uma versão mais longa uma vez. |
| Voz | `api/episode/gemini.py` | O modelo de voz gera o diálogo com as duas vozes, em blocos de cerca de 650 palavras. Se o Gemini estiver fora do ar, o código espera e tenta de novo (veja *Bom saber*). |
| Áudio | `api/episode/audio.py` | O ffmpeg junta os trechos, normaliza o volume e gera um OGG/Opus de 32 kbps (cerca de 4 MB para 15 minutos), o formato das mensagens de voz do Telegram. |
| Envio | `api/episode/telegram.py` | `sendVoice` com o título e a data na legenda (por ser mensagem de voz, o Telegram mostra o botão de velocidade 1x, 1,5x, 2x). Sai assim que fica pronto, sem esperar a hora cheia. Se algo falhar, chega uma mensagem dizendo em qual etapa. |

O episódio diário roda num serviço Cron do Railway (veja *Agendamento*).

## Configuração (uma vez só)

1. **Bot do Telegram:** no Telegram, abra o `@BotFather`, mande `/newbot`, escolha um
   nome e guarde o token que ele devolve. Depois abra o seu bot e mande `/start`.
2. **Chave do Gemini:** em [aistudio.google.com](https://aistudio.google.com), clique em
   *Get API key* e crie uma chave. O plano grátis não pede cartão.
3. **Banco:** crie o banco `news_podcast_db` no Postgres do Railway, como os outros,
   ponha a `NEWS_PODCAST_DATABASE_URL` também no serviço do backend (o admin usa o
   banco) e rode as migrations (`make migrate` com as URLs de produção).
4. **Descobrir o seu chat:** com o `TELEGRAM_BOT_TOKEN` no `.env`, rode na pasta
   `backend/` `uv run python manage.py news_podcast chat-id`. O bot te manda um número no
   Telegram: ele vai na variável `TELEGRAM_CHAT_ID` do serviço (veja *Agendamento*). Para
   mandar para um grupo, veja *Mandar para um grupo*.
5. **Agendamento:** crie o serviço no Railway (abaixo). Daí em diante ele roda sozinho,
   começa às 6h40 e envia perto das 7h.
6. **Testar:** no Railway, abra o serviço e clique em *Run now*, ou rode
   `railway cron run` na CLI.

## Agendamento (Railway)

Um serviço Cron no projeto do Railway, a partir do mesmo repositório:

1. *New → GitHub Repo* com este repositório. Em *Settings*: Root Directory `/backend`,
   branch `main`, Custom Start Command `python manage.py news_podcast episode
   --scheduled` e Cron Schedule `40 9 * * *` (6h40 em Brasília; o Railway usa UTC).
2. Em *Variables*: `RAILPACK_DEPLOY_APT_PACKAGES=ffmpeg` (instala o ffmpeg só neste
   serviço), `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
   `TELEGRAM_ADMIN_CHAT_ID` e `NEWS_PODCAST_DATABASE_URL`. O Django também exige, para
   subir, `SECRET_KEY`, `API_TOKEN_SECRET` (32 caracteres ou mais), `ESP32_DEVICE_KEY`,
   `OPEN_WEATHER_API_KEY`, `SERVER_URL`, `NGROK_URL`, `FRONT_END_URL`,
   `ENVIRONMENT=development` (assim ele não pede o `REDIS_URL`) e as outras quatro
   `*_DATABASE_URL`. Para essas, valores fictícios servem (as URLs de banco podem ser
   `sqlite:///dummy.db`), porque o podcast só usa o banco dele.

O episódio sai assim que fica pronto. O nome ("Resumo das 7") e o bom dia seguem a hora
cheia seguinte ao início da execução, e as notícias vão até a hora cheia anterior: com o
cron às 6h40, ele lê o que saiu até as 6h e chega perto das 7h. Para mudar o horário ou a
frequência, mude só o Cron Schedule, em UTC e uns 20 minutos antes da hora do episódio
(`40 21 * * *` envia perto das 19h de Brasília). Evite o episódio da meia-noite (cron
entre 23h e 0h de Brasília): ele chegaria antes da meia-noite, já com a data do dia
seguinte. Uma execução só começa se a anterior já terminou.

Para rodar na mão, use o *Run now* do serviço ou `railway cron run`. Como é o mesmo
comando do cron, ele respeita a pausa e lê as notícias até a hora cheia em que começou.
Rodando local sem `--scheduled`, ele lê as notícias até o momento em que começa.

## Mandar para um grupo

O bot só envia para a conversa do `TELEGRAM_CHAT_ID`. Quem só abre o bot e manda
`/start` não recebe nada. Para mais gente ouvir, use um grupo:

1. No Telegram, crie um grupo com as pessoas e adicione o bot (procure pelo @ dele).
2. Rode o `chat-id` (veja *Configuração*). Com o `TELEGRAM_CHAT_ID` ou o
   `TELEGRAM_ADMIN_CHAT_ID` no `.env`, o bot manda só para essa conversa a lista das
   conversas que viu nas últimas 24 horas, com o número de cada uma. O grupo aparece com
   👥 e um número negativo.
3. Troque `TELEGRAM_CHAT_ID` pelo número do grupo no serviço do Railway. Daí em diante o
   resumo vai para o grupo. Os avisos de erro vão para o `TELEGRAM_ADMIN_CHAT_ID` (o
   número da sua conversa com o bot), para não aparecerem no grupo; sem ele, vão para o
   grupo também.

Se o grupo não aparecer na lista (o Telegram só guarda as últimas 24 horas para o bot),
mande `/start@nome_do_bot` no grupo e rode de novo. Se o Telegram transformar o grupo em
supergrupo, o que acontece ao mudar algumas configurações dele, o número muda: repita os
passos 2 e 3.

## Configurações

Ficam no admin do Django, em *News podcast → Settings*. É uma linha só, que começa com os
valores do `config.py` e do `prompts.py`; depois disso, mudar esses arquivos não muda o
que está no banco. Cada mudança vale a partir da próxima execução, e um valor inválido
não salva: o admin mostra o erro no campo.

- **Paused:** as execuções do Railway (o cron e o *Run now*) terminam sem episódio.
- **Duração e velocidade:** a duração vale para o arquivo, já na velocidade escolhida.
  Com `1.25`, o roteiro fica 25% maior para caber no mesmo tempo, e a voz custa 25% a
  mais. O número de histórias acompanha a duração (uma a cada minuto e meio).
- **Limite:** o máximo da duração vezes a velocidade pode chegar a 30 minutos de fala
  (`MAX_SPEECH_MINUTES` no `config.py`). Cada pedido de voz gera uns 4 minutos e o plano
  grátis permite 10 pedidos por dia, então 30 minutos dão uns 8 pedidos. No plano pago,
  dá para aumentar esse limite.
- **Modelos e preços:** o modelo de texto, o reserva (opcional) e o de voz, cada um com
  o preço em US$ por milhão de tokens de entrada e de saída, da tabela do Google. O custo
  do histórico usa esses preços, então um modelo novo precisa do preço dele.
- **Prompts e estilos de voz:** o prompt da seleção, o do roteiro e o de alongamento
  (pedido uma vez, quando o roteiro vem curto), e os estilos da conversa e das manchetes
  da escalada. Cada prompt só aceita os `{campos}` listados embaixo dele, sem
  formatação (`{today}` funciona, `{today:%d}` não); uma chave literal se escreve `{{`
  ou `}}`. Se mudar o estilo ou a voz, ajuste
  `NATURAL_WORDS_PER_MINUTE` (palavras por minuto da voz antes do ffmpeg); senão o
  episódio sai mais curto ou mais longo que o previsto.

## Histórico

Em *News podcast → Episodes*, uma linha por execução: hora de início (de Brasília),
status (enviado, falhou ou, com `--no-send`, não enviado), duração, custo no plano pago
em reais e, se falhou, a etapa e o erro. A página de cada execução mostra os tokens de
cada resposta do Gemini. O áudio não fica guardado. O topo da lista mostra o custo total
do que está filtrado (por mês ou por status). Uma execução pausada não aparece, e uma
que falha no meio grava o custo do que já rodou.

## Ajustes

- **Feeds:** exporte de novo no Feeder e substitua o `feeds.opml`. Use só sites sem
  paywall e confira se o domínio está em `FULL_TEXT_DOMAINS` (`config.py`). Fora dessa
  lista, a matéria entra só com o título e o resumo do RSS.
- **Apresentadores e as vozes deles:** `HOSTS` no `config.py`.
- **Dólar usado para mostrar os custos em reais:** `BRL_PER_USD` (fixo) no `config.py`.

Para rodar localmente sem enviar, a partir da pasta `backend/`, com ffmpeg instalado, as
chaves e o `NEWS_PODCAST_DATABASE_URL` no `.env` e as migrations rodadas:

```
uv run python manage.py news_podcast episode --no-send
```

O áudio e os JSON da seleção e do roteiro ficam em `backend/news_podcast_output/`, que
está no `.gitignore`.

## Bom saber

- O custo do histórico é o do plano pago; no plano grátis, a execução não custa nada. Os
  preços iniciais são promocionais até 31/12/2026 e dobram em 1/1/2027 (texto 1,50 e
  7,50; voz 1,00 e 12,00 por milhão de tokens): atualize no admin nesse dia.
- A velocidade acelera o próprio arquivo com o filtro `atempo` do ffmpeg. O botão de
  velocidade do player do Telegram (1x, 1,5x, 2x) continua valendo, e as duas
  velocidades se multiplicam.
- Se o modelo de texto estiver sobrecarregado, o texto é feito com o reserva, e o resto
  da execução já vai direto para ele.
- A voz não tem reserva: se o Gemini estiver fora do ar, o código espera 10 minutos e
  depois 20 e tenta de novo, e o episódio chega mais tarde na mesma medida. Se ainda
  falhar, ou se a cota do dia acabar, o episódio do dia não sai e chega uma mensagem de
  erro no Telegram.
