# news_podcast · Resumo das 7

Todo dia chega no Telegram uma mensagem de voz com dois apresentadores (Bia e Léo)
contando o que aconteceu nas 24 horas anteriores, a partir dos feeds do `feeds.opml`. No
padrão, ela chega às 7h e tem de 12 a 18 minutos (de 8 a 12 em 1,5x). Horário, duração e
velocidade mudam por variáveis no GitHub (veja *Variáveis*). Logo depois do áudio chega
uma mensagem curta com as fontes usadas e o custo do dia.

O app não tem models nem banco de dados, então não precisa de um `news_podcast_db` no
`DATABASES` nem de mudanças no Makefile. Ele só expõe um management command.

## Como funciona

| Etapa | Arquivo | O que acontece |
|---|---|---|
| Feeds | `api/episode/feeds.py` | Lê o OPML exportado do Feeder, baixa os 9 feeds em paralelo e mantém só as 24 horas que terminam na hora cheia anterior ao envio (no padrão, das 6h de ontem às 6h de hoje). |
| Seleção | `service.py` + `prompts.py` | O Gemini 3.8 Flash recebe todas as manchetes, junta as que falam do mesmo fato, aplica as regras editoriais e escolhe uma história para cada minuto e meio de episódio (de 8 a 12 no padrão), com o tempo de cada uma. |
| Leitura | `api/episode/articles.py` | Para cada história, lê o texto completo de até 3 veículos (o ICL vem primeiro). Os demais veículos que deram a notícia entram como manchete. Todos os feeds são de sites sem paywall. |
| Roteiro | `service.py` + `prompts.py` | O Gemini escreve o diálogo com 170 palavras por minuto de episódio, vezes a velocidade (de 2.040 a 3.060 palavras no padrão), abrindo com uma escalada de 3 a 5 manchetes curtas, como nos telejornais. Se vier curto demais, pede uma versão mais longa uma vez. |
| Voz | `api/episode/gemini.py` | O Gemini 3.8 Flash-Lite TTS gera o diálogo com as duas vozes, em blocos de cerca de 650 palavras. Se o Gemini estiver fora do ar, o código espera e tenta de novo (veja *Bom saber*). |
| Áudio | `api/episode/audio.py` | O ffmpeg junta os trechos, normaliza o volume e gera um OGG/Opus de 32 kbps (cerca de 4 MB para 15 minutos), o formato das mensagens de voz do Telegram. |
| Envio | `api/episode/telegram.py` | `sendVoice` só com o título (por ser mensagem de voz, o Telegram mostra o botão de velocidade 1x, 1,5x, 2x) e, logo depois, uma mensagem de texto com fontes e custos, que fica mais larga que uma legenda. Na execução agendada, espera o horário de envio. Se algo falhar, chega uma mensagem dizendo em qual etapa. |

Por que GitHub Actions e não Railway: o repositório é público, então os minutos do
Actions são de graça; o runner já tem um botão para rodar na hora e mostra o log de cada
execução; e o job roda isolado, sem mexer no deploy nem na imagem do serviço web. Se um
dia preferir o Railway, basta criar um serviço Cron no mesmo repositório com o Start
Command `python manage.py news_podcast episode --scheduled`, o ffmpeg no build e as
mesmas variáveis. Lá o início fica fixo no cron do serviço (`10 9 * * *` é 6h10 em
Brasília), porque o job `check-time` só existe no GitHub.

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
6. **Escolher (opcional):** na aba *Variables* da mesma tela, crie só as variáveis que
   quiser mudar (veja *Variáveis*), como a voz em `NEWS_PODCAST_VOICE`.
7. **Testar:** rode com a ação `episode`. Daí em diante ele roda sozinho: começa aos 10
   minutos da hora anterior ao envio (6h10 no padrão) e envia no horário.

## Variáveis

Todas são opcionais e ficam em *Settings → Secrets and variables → Actions → aba
Variables*. Sem a variável, vale o padrão. Um valor em formato errado não cai no padrão
em silêncio: o episódio falha e chega no Telegram uma mensagem dizendo o que corrigir.

| Variável | Padrão | Exemplo | O que muda |
|---|---|---|---|
| `NEWS_PODCAST_SEND_AT` | `07:00` | `21:00` | Horário de envio, no horário de Brasília (HH:MM). |
| `NEWS_PODCAST_MINUTES` | `12-18` | `8-12` | Duração do áudio que chega no Telegram, em minutos (mínimo-máximo, a partir de 5). |
| `NEWS_PODCAST_SPEECH_SPEED` | `1` | `1.25` | Velocidade do arquivo, de 0.5 a 2 (também aceita `1,25` e `1.25x`). |
| `NEWS_PODCAST_VOICE` | `gemini-flash-lite` | `gemini-flash` | Voz: `gemini-flash`, `gemini-flash-lite` ou `microsoft`. |
| `NEWS_PODCAST_GEMINI_PLAN` | `free` | `paid` | Com `paid`, a mensagem mostra o custo como cobrado. Use se ativar o pagamento no Google. |

- **Horário:** o agendamento do GitHub não lê variáveis, então o workflow acorda toda
  hora, aos 10 minutos. O job `check-time` lê `NEWS_PODCAST_SEND_AT` e só deixa o
  episódio rodar aos 10 minutos da hora anterior ao envio (20h10 para `21:00`). Nas
  outras 23 execuções do dia, o job do episódio aparece como pulado (*skipped*) em
  poucos segundos e sem custo, porque o repositório é público. O nome do podcast
  acompanha a hora (Resumo das 7, Resumo das 21, Resumo do meio-dia), e o bom dia vira
  boa tarde ou boa noite.
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
- Se o GitHub atrasar uma execução agendada em uma hora ou mais (raro, em dias de muita
  carga), o `check-time` já não reconhece a hora certa e o episódio daquele dia não sai.
- Se o Gemini 3.8 Flash estiver sobrecarregado, o texto é feito com o Gemini 3.6 Flash,
  e o resto da execução já vai direto para ele.
- A voz não tem reserva: se o Gemini estiver fora do ar, o código espera 10 minutos e
  depois 20 e tenta de novo. Se ainda falhar, ou se a cota do dia acabar, o episódio do
  dia não sai e chega uma mensagem de erro no Telegram.
- A voz da Microsoft (`microsoft_voice.py`, via edge-tts) vem do serviço de leitura em voz
  alta do Edge, que não é uma API oficial. Ela só é usada se você escolher
  `NEWS_PODCAST_VOICE=microsoft`.
