# news_podcast · Resumo das 7

Todo dia chega no Telegram uma mensagem de voz com dois apresentadores (Bia e Léo)
contando o que aconteceu nas 24 horas anteriores, a partir dos feeds do `feeds.opml`. Ela
chega às 7h e, no padrão, tem de 12 a 18 minutos (de 8 a 12 em 1,5x). Duração e
velocidade mudam por variáveis no GitHub (veja *Variáveis*). O episódio é só essa
mensagem de voz: as fontes usadas e o custo do dia ficam no log da execução, no Actions.

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
| Envio | `api/episode/telegram.py` | `sendVoice` com o título e a data na legenda (por ser mensagem de voz, o Telegram mostra o botão de velocidade 1x, 1,5x, 2x). É a única mensagem do episódio; fontes e custos ficam só no log. Na execução agendada, espera dar 7h para enviar. Se algo falhar, chega uma mensagem dizendo em qual etapa. |

Por que GitHub Actions e não Railway: o repositório é público, então os minutos do
Actions são de graça; o runner já tem um botão para rodar na hora e mostra o log de cada
execução; e o job roda isolado, sem mexer no deploy nem na imagem do serviço web. Se um
dia preferir o Railway, basta criar um serviço Cron no mesmo repositório com o Start
Command `python manage.py news_podcast episode --scheduled`, o cron `10 9 * * *`, o
ffmpeg no build e as mesmas variáveis.

## Configuração (uma vez só)

1. **Bot do Telegram:** no Telegram, abra o `@BotFather`, mande `/newbot`, escolha um
   nome e guarde o token que ele devolve. Depois abra o seu bot e mande `/start`.
2. **Chave do Gemini:** em [aistudio.google.com](https://aistudio.google.com), clique em
   *Get API key* e crie uma chave. O plano grátis não pede cartão.
3. **Secrets no GitHub:** em *Settings → Secrets and variables → Actions → New
   repository secret*, crie `GEMINI_API_KEY` e `TELEGRAM_BOT_TOKEN`.
4. **Descobrir o seu chat:** em *Actions → News podcast → Run workflow*, escolha a ação
   `chat-id`. O bot te manda um número no Telegram; salve como o secret
   `TELEGRAM_CHAT_ID`. Para mandar para um grupo, veja *Mandar para um grupo*.
5. **Ouvir as vozes:** rode de novo com a ação `samples`. Chegam 4 amostras do mesmo
   trecho, cada uma com o custo mensal estimado.
6. **Escolher (opcional):** na aba *Variables* da mesma tela, crie só as variáveis que
   quiser mudar (veja *Variáveis*), como a voz em `NEWS_PODCAST_VOICE`.
7. **Testar:** rode com a ação `episode`. Daí em diante ele roda sozinho: começa às
   6h10 e envia às 7h.

## Mandar para um grupo

O bot só envia para a conversa do `TELEGRAM_CHAT_ID`. Quem só abre o bot e manda
`/start` não recebe nada. Para mais gente ouvir, use um grupo:

1. No Telegram, crie um grupo com as pessoas e adicione o bot (procure pelo @ dele).
2. Em *Actions → News podcast → Run workflow*, rode a ação `chat-id`. Como o
   `TELEGRAM_CHAT_ID` já existe, o bot manda só para essa conversa a lista das conversas
   que viu nas últimas 24 horas, com o número de cada uma. O grupo aparece com 👥 e um
   número negativo.
3. Troque o secret `TELEGRAM_CHAT_ID` pelo número do grupo. Daí em diante o resumo e os
   avisos de erro vão para o grupo.

Se o grupo não aparecer na lista (o Telegram só guarda as últimas 24 horas para o bot),
mande `/start@nome_do_bot` no grupo e rode de novo. Se o Telegram transformar o grupo em
supergrupo, o que acontece ao mudar algumas configurações dele, o número muda: repita os
passos 2 e 3.

## Variáveis

Todas são opcionais e ficam em *Settings → Secrets and variables → Actions → aba
Variables*. Sem a variável, vale o padrão. Um valor em formato errado não cai no padrão
em silêncio: o episódio falha e chega no Telegram uma mensagem dizendo o que corrigir.

| Variável | Padrão | Exemplo | O que muda |
|---|---|---|---|
| `NEWS_PODCAST_MINUTES` | `12-18` | `8-12` | Duração do áudio que chega no Telegram, em minutos (mínimo-máximo, a partir de 5). |
| `NEWS_PODCAST_SPEECH_SPEED` | `1` | `1.25` | Velocidade do arquivo, de 0.5 a 2 (também aceita `1,25` e `1.25x`). |
| `NEWS_PODCAST_VOICE` | `gemini-flash-lite` | `gemini-flash` | Voz: `gemini-flash`, `gemini-flash-lite` ou `microsoft`. |
| `NEWS_PODCAST_GEMINI_PLAN` | `free` | `paid` | Com `paid`, o log mostra o custo como cobrado. Use se ativar o pagamento no Google. |

- **Horário (fixo por enquanto):** o agendamento do GitHub não lê variáveis. A v2.3.0
  tentou acordar o workflow toda hora e decidir a hora certa num job à parte, mas o
  GitHub disparou só 1 das cerca de 10 execuções da primeira noite e o episódio não saiu.
  Por isso o horário voltou a ser fixo: o cron `10 9 * * *` (6h10 em Brasília) e o
  `NEWS_PODCAST_SEND_AT: "07:00"` ficam no próprio `.github/workflows/news_podcast.yml`.
  Uma variável `NEWS_PODCAST_SEND_AT` criada no GitHub é ignorada. Para mudar o horário,
  edite os dois juntos. O código já aceita outros horários (o nome do podcast e o bom
  dia acompanham), para quando o agendamento for para o Railway.
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

Para rodar localmente sem enviar, com ffmpeg instalado e as chaves no `.env`:

```
uv run python manage.py news_podcast episode --no-send
```

O áudio e os JSON de cada etapa ficam em `news_podcast_output/`, que está no `.gitignore`.

## Bom saber

- Os logs do Actions de um repositório público são públicos. Eles mostram as manchetes
  escolhidas, nunca as chaves, que o GitHub mascara.
- O GitHub pausa agendamentos em repositório público que fica 60 dias sem nenhuma
  atividade.
- Os preços do Gemini em `PRICES` são promocionais até 31/12/2026 e dobram em
  1/1/2027. Se o Google mudar a tabela, é só atualizar ali.
- `NEWS_PODCAST_SPEECH_SPEED` acelera o próprio arquivo com o filtro `atempo` do
  ffmpeg. O botão de velocidade do player do Telegram (1x, 1,5x, 2x) continua valendo, e
  as duas velocidades se multiplicam.
- O GitHub não garante o horário dos agendamentos: em momentos de carga ele atrasa ou até
  descarta execuções. Se a das 6h10 atrasar, o episódio sai assim que ficar pronto; se
  for descartada, o dia fica sem episódio (dá para rodar na mão em *Run workflow*).
- Se o Gemini 3.8 Flash estiver sobrecarregado, o texto é feito com o Gemini 3.6 Flash,
  e o resto da execução já vai direto para ele.
- A voz não tem reserva: se o Gemini estiver fora do ar, o código espera 10 minutos e
  depois 20 e tenta de novo. Se ainda falhar, ou se a cota do dia acabar, o episódio do
  dia não sai e chega uma mensagem de erro no Telegram.
- A voz da Microsoft (`microsoft_voice.py`, via edge-tts) vem do serviço de leitura em voz
  alta do Edge, que não é uma API oficial. Ela só é usada se você escolher
  `NEWS_PODCAST_VOICE=microsoft`.
