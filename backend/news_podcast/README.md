# news_podcast · Resumo das 7

Todo dia chega no Telegram uma mensagem de voz com dois apresentadores (Bia e Léo)
contando o que aconteceu nas 24 horas anteriores, a partir dos feeds do `feeds.opml`. Ela
chega às 7h e, no padrão, tem de 12 a 18 minutos (de 8 a 12 em 1,5x). Duração e
velocidade mudam por variáveis (veja *Variáveis*). O episódio é só essa mensagem de voz:
as fontes usadas e o custo do dia ficam no log da execução, no Railway (ou no Actions,
quando roda na mão).

O app não tem models nem banco de dados, então não precisa de um `news_podcast_db` no
`DATABASES` nem de mudanças no Makefile. Ele só expõe um management command.

## Como funciona

| Etapa | Arquivo | O que acontece |
|---|---|---|
| Feeds | `api/episode/feeds.py` | Lê o OPML exportado do Feeder, baixa os 9 feeds em paralelo e mantém só o que saiu entre 6h de ontem e 6h de hoje. |
| Seleção | `service.py` + `prompts.py` | O Gemini 3.8 Flash recebe todas as manchetes, junta as que falam do mesmo fato, aplica as regras editoriais e escolhe uma história para cada minuto e meio de episódio (de 8 a 12 no padrão), com o tempo de cada uma. |
| Leitura | `api/episode/articles.py` | Para cada história, lê o texto completo de até 3 veículos (o ICL vem primeiro). Os demais veículos que deram a notícia entram como manchete. Todos os feeds são de sites sem paywall. |
| Roteiro | `service.py` + `prompts.py` | O Gemini escreve o diálogo com 170 palavras por minuto de episódio, vezes a velocidade (de 2.040 a 3.060 palavras no padrão), abrindo com uma escalada de 3 a 5 manchetes curtas, como nos telejornais. Se vier curto demais, pede uma versão mais longa uma vez. |
| Voz | `api/episode/gemini.py` | O Gemini 3.8 Flash-Lite TTS gera o diálogo com as duas vozes, em blocos de cerca de 650 palavras. Se o Gemini estiver fora do ar, o código espera e tenta de novo (veja *Bom saber*). |
| Áudio | `api/episode/audio.py` | O ffmpeg junta os trechos, normaliza o volume e gera um OGG/Opus de 32 kbps (cerca de 4 MB para 15 minutos), o formato das mensagens de voz do Telegram. |
| Envio | `api/episode/telegram.py` | `sendVoice` com o título e a data na legenda (por ser mensagem de voz, o Telegram mostra o botão de velocidade 1x, 1,5x, 2x). Na execução agendada, espera dar 7h para enviar. Se algo falhar, chega uma mensagem dizendo em qual etapa. |

O episódio diário roda num serviço Cron do Railway (veja *Agendamento*). Ele rodava no
GitHub Actions, mas o GitHub atrasava os agendamentos em horas ou os descartava. O
workflow do GitHub ficou para rodar na mão (*Actions → News podcast → Run workflow*).

## Configuração (uma vez só)

1. **Bot do Telegram:** no Telegram, abra o `@BotFather`, mande `/newbot`, escolha um
   nome e guarde o token que ele devolve. Depois abra o seu bot e mande `/start`.
2. **Chave do Gemini:** em [aistudio.google.com](https://aistudio.google.com), clique em
   *Get API key* e crie uma chave. O plano grátis não pede cartão.
3. **Secrets no GitHub:** em *Settings → Secrets and variables → Actions → New
   repository secret*, crie `GEMINI_API_KEY` e `TELEGRAM_BOT_TOKEN`. Eles servem para as
   execuções na mão; o Railway tem as suas próprias variáveis (veja *Agendamento*).
4. **Descobrir o seu chat:** em *Actions → News podcast → Run workflow*, escolha a ação
   `chat-id`. O bot te manda um número no Telegram; salve como o secret
   `TELEGRAM_CHAT_ID`. Para mandar para um grupo, veja *Mandar para um grupo*.
5. **Escolher (opcional):** na aba *Variables* da mesma tela, crie só as variáveis que
   quiser mudar (veja *Variáveis*), como a duração em `NEWS_PODCAST_MINUTES`.
6. **Testar:** rode com a ação `episode`. Depois, configure o *Agendamento*: daí em
   diante ele roda sozinho, começa às 6h10 e envia às 7h.

## Agendamento (Railway)

Um serviço Cron no projeto do Railway, a partir do mesmo repositório:

1. *New → GitHub Repo* com este repositório. Em *Settings*: Root Directory `/backend`,
   branch `main`, Custom Start Command `python manage.py news_podcast episode
   --scheduled` e Cron Schedule `10 9 * * *` (6h10 em Brasília; o Railway usa UTC).
2. Em *Variables*: `RAILPACK_DEPLOY_APT_PACKAGES=ffmpeg` (instala o ffmpeg só neste
   serviço; com o builder Nixpacks, é `NIXPACKS_APT_PKGS=ffmpeg`), `GEMINI_API_KEY`,
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_ADMIN_CHAT_ID`,
   `NEWS_PODCAST_SEND_AT=07:00`, as opcionais de *Variáveis* e os valores fictícios que o
   Django exige: copie os do `env` do `.github/workflows/news_podcast.yml` (o app não usa
   banco).

O cron e o `NEWS_PODCAST_SEND_AT` andam juntos: a execução começa uma hora antes e espera
dar o horário para enviar. Uma execução só começa se a anterior já terminou.

## Mandar para um grupo

O bot só envia para a conversa do `TELEGRAM_CHAT_ID`. Quem só abre o bot e manda
`/start` não recebe nada. Para mais gente ouvir, use um grupo:

1. No Telegram, crie um grupo com as pessoas e adicione o bot (procure pelo @ dele).
2. Em *Actions → News podcast → Run workflow*, rode a ação `chat-id`. Como o
   `TELEGRAM_CHAT_ID` já existe, o bot manda só para essa conversa a lista das conversas
   que viu nas últimas 24 horas, com o número de cada uma. O grupo aparece com 👥 e um
   número negativo.
3. Troque `TELEGRAM_CHAT_ID` pelo número do grupo, no GitHub e no Railway. Daí em diante
   o resumo vai para o grupo. Os avisos de erro e a lista de conversas vão para o
   `TELEGRAM_ADMIN_CHAT_ID` (o número da sua conversa com o bot), para não aparecerem no
   grupo; sem ele, vão para o grupo também.

Se o grupo não aparecer na lista (o Telegram só guarda as últimas 24 horas para o bot),
mande `/start@nome_do_bot` no grupo e rode de novo. Se o Telegram transformar o grupo em
supergrupo, o que acontece ao mudar algumas configurações dele, o número muda: repita os
passos 2 e 3.

## Variáveis

Todas são opcionais. Crie as mesmas no Railway (execução diária) e no GitHub, em
*Settings → Secrets and variables → Actions → aba Variables* (execuções na mão). Sem a
variável, vale o padrão. Um valor em formato errado não cai no padrão
em silêncio: o episódio falha e chega no Telegram uma mensagem dizendo o que corrigir.

| Variável | Padrão | Exemplo | O que muda |
|---|---|---|---|
| `NEWS_PODCAST_MINUTES` | `12-18` | `8-12` | Duração do áudio que chega no Telegram, em minutos (mínimo-máximo, a partir de 5). |
| `NEWS_PODCAST_SPEECH_SPEED` | `1` | `1.25` | Velocidade do arquivo, de 0.5 a 2 (também aceita `1,25` e `1.25x`). |

- **Horário:** para mudar, ajuste juntos o Cron Schedule do serviço no Railway (uma
  hora antes, em UTC) e o `NEWS_PODCAST_SEND_AT`. O nome do podcast e o bom dia
  acompanham o horário.
- **Duração e velocidade:** a duração vale para o arquivo, já na velocidade escolhida.
  Com `1.25`, o roteiro fica 25% maior para caber no mesmo tempo, e a voz custa 25% a
  mais. O número de histórias acompanha a duração (uma a cada minuto e meio).
- **Limite:** o máximo da duração vezes a velocidade pode chegar a 30 minutos de fala
  (`MAX_SPEECH_MINUTES` no `config.py`). Cada pedido de voz gera uns 4 minutos e o plano
  grátis permite 10 pedidos por dia, então 30 minutos dão uns 8 pedidos. No plano pago,
  dá para aumentar esse limite.
- Para rodar localmente, as mesmas variáveis funcionam no `.env`.

## Ajustes

- **Feeds:** exporte de novo no Feeder e substitua o `feeds.opml`. Use só sites sem
  paywall e confira se o domínio está em `FULL_TEXT_DOMAINS` (`config.py`). Fora dessa
  lista, a matéria entra só com o título e o resumo do RSS.
- **Apresentadores, vozes, modelos, preços e os padrões das variáveis:**
  `api/episode/config.py`.
- **Ritmo e tom da voz:** o estilo pedido ao Gemini fica em `TTS_STYLE` (conversa) e em
  `HEADLINE_TTS_STYLE` (manchetes da escalada, lidas com mais ênfase). Se mudar o estilo
  ou a voz, ajuste `NATURAL_WORDS_PER_MINUTE` (palavras por minuto da voz antes do
  ffmpeg); senão o episódio sai mais curto ou mais longo que o previsto.
- **Regras editoriais (o que entra e o que não entra):** `api/episode/prompts.py`.
- **Dólar usado para mostrar os custos em reais:** `BRL_PER_USD` (fixo) no `config.py`.

Para rodar localmente sem enviar, a partir da pasta `backend/`, com ffmpeg instalado e as
chaves no `.env`:

```
uv run python manage.py news_podcast episode --no-send
```

O áudio e os JSON da seleção e do roteiro ficam em `backend/news_podcast_output/`, que
está no `.gitignore`.

## Bom saber

- Os logs do Actions de um repositório público são públicos. Os das execuções na mão
  mostram as manchetes escolhidas, nunca as chaves, que o GitHub mascara.
- O custo no log é o do plano pago; no plano grátis, a execução não custa nada. Os preços
  do Gemini em `PRICES` são promocionais até 31/12/2026 e dobram em 1/1/2027. Se o
  Google mudar a tabela, é só atualizar ali.
- `NEWS_PODCAST_SPEECH_SPEED` acelera o próprio arquivo com o filtro `atempo` do
  ffmpeg. O botão de velocidade do player do Telegram (1x, 1,5x, 2x) continua valendo, e
  as duas velocidades se multiplicam.
- Se o Gemini 3.8 Flash estiver sobrecarregado, o texto é feito com o Gemini 3.6 Flash,
  e o resto da execução já vai direto para ele.
- A voz não tem reserva: se o Gemini estiver fora do ar, o código espera 10 minutos e
  depois 20 e tenta de novo. Se ainda falhar, ou se a cota do dia acabar, o episódio do
  dia não sai e chega uma mensagem de erro no Telegram.
