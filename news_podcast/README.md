# news_podcast · Resumo das 7

Todo dia, às 7h, chega no Telegram uma mensagem de voz de 12 a 18 minutos (de 8 a
12 em 1,5x) com dois apresentadores (Bia e Léo) contando o que aconteceu nas 24 horas anteriores, a
partir dos feeds do `feeds.opml`. Logo depois do áudio chega uma mensagem curta com as fontes usadas e o custo do dia.

O app não tem models nem banco de dados, então não precisa de um `news_podcast_db` no
`DATABASES` nem de mudanças no Makefile. Ele só expõe um management command.

## Como funciona

| Etapa | Arquivo | O que acontece |
|---|---|---|
| Feeds | `api/episode/feeds.py` | Lê o OPML exportado do Feeder, baixa os 9 feeds em paralelo e mantém só o que saiu entre 6h de ontem e 6h de hoje. |
| Seleção | `service.py` + `prompts.py` | O Gemini 3.8 Flash recebe todas as manchetes, junta as que falam do mesmo fato, aplica as regras editoriais e escolhe de 8 a 12 histórias, com o tempo de cada uma. |
| Leitura | `api/episode/articles.py` | Para cada história, lê o texto completo de até 3 veículos (o ICL vem primeiro). Os demais veículos que deram a notícia entram como manchete. Todos os feeds são de sites sem paywall. |
| Roteiro | `service.py` + `prompts.py` | O Gemini escreve o diálogo, com cerca de 2.000 a 3.100 palavras, abrindo com uma escalada de 3 a 5 manchetes curtas, como nos telejornais. Se vier curto demais, pede uma versão mais longa uma vez. |
| Voz | `api/episode/gemini.py` | O Gemini 3.8 Flash-Lite TTS gera o diálogo com as duas vozes, em blocos de cerca de 650 palavras. Se o Gemini estiver fora do ar, o código espera e tenta de novo (veja *Bom saber*). |
| Áudio | `api/episode/audio.py` | O ffmpeg junta os trechos, normaliza o volume e gera um OGG/Opus de 32 kbps (cerca de 4 MB para 15 minutos), o formato das mensagens de voz do Telegram. |
| Envio | `api/episode/telegram.py` | `sendVoice` só com o título (por ser mensagem de voz, o Telegram mostra o botão de velocidade 1x, 1,5x, 2x) e, logo depois, uma mensagem de texto com fontes e custos, que fica mais larga que uma legenda. Na execução agendada, espera dar 7h para enviar. Se algo falhar, chega uma mensagem dizendo em qual etapa. |

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
   `TELEGRAM_CHAT_ID`.
5. **Ouvir as vozes:** rode de novo com a ação `samples`. Chegam 4 amostras do mesmo
   trecho, cada uma com o custo mensal estimado.
6. **Escolher (opcional):** na aba *Variables* da mesma tela, crie
   `NEWS_PODCAST_VOICE` com `gemini-flash`, `gemini-flash-lite` ou `microsoft` (sem ela,
   vale o `DEFAULT_VOICE` do `config.py`, hoje `gemini-flash-lite`). Se ativar
   o pagamento no Google, crie também `NEWS_PODCAST_GEMINI_PLAN` com `paid`, para a
   legenda mostrar o custo como cobrado.
7. **Testar:** rode com a ação `episode`. Daí em diante ele roda sozinho: começa às
   6h10 e envia às 7h.

## Ajustes

- **Feeds:** exporte de novo no Feeder e substitua o `feeds.opml`. Use só sites sem
  paywall e confira se o domínio está em `FULL_TEXT_DOMAINS` (`config.py`). Fora dessa
  lista, a matéria entra só com o título e o resumo do RSS.
- **Duração, velocidade (`SPEECH_SPEED`), apresentadores, vozes, modelos e preços:**
  `api/episode/config.py`.
- **Ritmo e tom da voz:** o estilo pedido ao Gemini fica em `TTS_STYLE` (conversa) e em
  `HEADLINE_TTS_STYLE` (manchetes da escalada, lidas com mais ênfase). Se mudar o estilo
  ou a voz, ajuste `NATURAL_WORDS_PER_MINUTE` (palavras por minuto da voz antes do
  ffmpeg); senão o episódio sai mais curto ou mais longo que o previsto.
- **Regras editoriais (o que entra e o que não entra):** `api/episode/prompts.py`.
- **Dólar usado para mostrar os custos em reais:** `BRL_PER_USD` (fixo) no `config.py`.
- **Horário:** o cron do `.github/workflows/news_podcast.yml` (em UTC) e
  `NEWS_CUTOFF`/`SEND_AT` no config.

Para rodar localmente sem enviar, com ffmpeg instalado e as chaves no `.env`:

```
uv run python manage.py news_podcast episode --no-send
```

O MP3 e os JSON de cada etapa ficam em `news_podcast_output/`, que está no `.gitignore`.

## Bom saber

- Os logs do Actions de um repositório público são públicos. Eles mostram as manchetes
  escolhidas, nunca as chaves, que o GitHub mascara.
- O GitHub pausa agendamentos em repositório público que fica 60 dias sem nenhuma
  atividade.
- Os preços do Gemini em `PRICES` são promocionais até 31/12/2026 e dobram em
  1/1/2027. Se o Google mudar a tabela, é só atualizar ali.
- A velocidade é escolhida no player do Telegram. Se um dia preferir o arquivo já
  acelerado, o `SPEECH_SPEED` do `config.py` aplica o filtro `atempo` do ffmpeg. O custo
  não muda, porque o Gemini cobra pelo áudio que gera, em velocidade normal.
- Se o Gemini 3.8 Flash estiver sobrecarregado, o texto é feito com o Gemini 3.6 Flash,
  e o resto da execução já vai direto para ele.
- A voz não tem reserva: se o Gemini estiver fora do ar, o código espera 10 minutos e
  depois 20 e tenta de novo. Se ainda falhar, ou se a cota do dia acabar, o episódio do
  dia não sai e chega uma mensagem de erro no Telegram.
- A voz da Microsoft (`microsoft_voice.py`, via edge-tts) vem do serviço de leitura em voz
  alta do Edge, que não é uma API oficial. Ela só é usada se você escolher
  `NEWS_PODCAST_VOICE=microsoft`.
