# news_podcast · Resumo das 7

Todo dia, às 7h, chega no Telegram uma mensagem de voz de 12 a 18 minutos com dois
apresentadores (Bia e Léo) contando o que aconteceu nas 24 horas anteriores, a partir dos
feeds do `feeds.opml`. O episódio é só essa mensagem de voz: as fontes usadas e o custo do
dia ficam no log da execução, no Actions.

O app não tem models nem banco de dados, então não precisa de um `news_podcast_db` no
`DATABASES` nem de mudanças no Makefile. Ele só expõe um management command.

## Como funciona

| Etapa | Arquivo | O que acontece |
|---|---|---|
| Feeds | `api/episode/feeds.py` | Lê o OPML exportado do Feeder, baixa os 9 feeds em paralelo e mantém só o que saiu entre 6h de ontem e 6h de hoje. |
| Seleção | `service.py` + `prompts.py` | O Gemini 3.8 Flash recebe todas as manchetes, junta as que falam do mesmo fato, aplica as regras editoriais e escolhe de 8 a 12 histórias (uma para cada minuto e meio de episódio), com o tempo de cada uma. |
| Leitura | `api/episode/articles.py` | Para cada história, lê o texto completo de até 3 veículos (o ICL vem primeiro). Os demais veículos que deram a notícia entram como manchete. Todos os feeds são de sites sem paywall. |
| Roteiro | `service.py` + `prompts.py` | O Gemini escreve o diálogo com 170 palavras por minuto de episódio (de 2.040 a 3.060 palavras), abrindo com uma escalada de 3 a 5 manchetes curtas, como nos telejornais. Se vier curto demais, pede uma versão mais longa uma vez. |
| Voz | `api/episode/gemini.py` | O Gemini 3.8 Flash-Lite TTS gera o diálogo com as duas vozes, em blocos de cerca de 650 palavras. Se o Gemini estiver fora do ar, o código espera e tenta de novo (veja *Bom saber*). |
| Áudio | `api/episode/audio.py` | O ffmpeg junta os trechos, normaliza o volume e gera um OGG/Opus de 32 kbps (cerca de 4 MB para 15 minutos), o formato das mensagens de voz do Telegram. |
| Envio | `api/episode/telegram.py` | `sendVoice` com o título e a data na legenda (por ser mensagem de voz, o Telegram mostra o botão de velocidade 1x, 1,5x, 2x). Na execução agendada, espera dar 7h para enviar. Se algo falhar, chega uma mensagem dizendo em qual etapa. |

Por que GitHub Actions e não Railway: o repositório é público, então os minutos do
Actions são de graça; o runner já tem um botão para rodar na hora e mostra o log de cada
execução; e o job roda isolado, sem mexer no deploy nem na imagem do serviço web. Se um
dia preferir o Railway, basta criar um serviço Cron no mesmo repositório com o Start
Command `python manage.py news_podcast --scheduled`, o cron `10 9 * * *`, o ffmpeg no
build e os mesmos secrets como variáveis de ambiente.

## Configuração (uma vez só)

1. **Bot do Telegram:** no Telegram, abra o `@BotFather`, mande `/newbot`, escolha um
   nome e guarde o token que ele devolve.
2. **Chave do Gemini:** em [aistudio.google.com](https://aistudio.google.com), clique em
   *Get API key* e crie uma chave. O plano grátis não pede cartão.
3. **Descobrir o chat:** crie um grupo com quem vai ouvir, adicione o bot e mande uma
   mensagem no grupo (para receber só você, mande `/start` para o bot). Abra
   `https://api.telegram.org/bot<TOKEN>/getUpdates` no navegador e copie o `chat.id` da
   conversa. O de um grupo é negativo.
4. **Secrets no GitHub:** em *Settings → Secrets and variables → Actions → New
   repository secret*, crie `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`.
5. **Testar:** em *Actions → News podcast → Run workflow*. Daí em diante ele roda
   sozinho: começa às 6h10 e envia às 7h.

Se o Telegram transformar o grupo em supergrupo, o que acontece ao mudar algumas
configurações dele, o número muda: leia o `getUpdates` de novo e troque o secret.

## Ajustes

- **Horário:** fixo. Para mudar, edite juntos o cron `10 9 * * *` (6h10 em Brasília) do
  `.github/workflows/news_podcast.yml`, `NEWS_CUTOFF`, `SEND_AT` e `PODCAST_NAME` no
  `config.py` e o "7h" e o "bom dia" do `SCRIPT_PROMPT`. Não use um cron de hora em hora:
  a v2.3.0 tentou, o GitHub disparou só 1 de cerca de 10 execuções e o episódio não saiu.
- **Duração, apresentadores, vozes, modelos e preços:** `api/episode/config.py`. O número
  de histórias acompanha a duração (uma a cada minuto e meio).
- **Feeds:** exporte de novo no Feeder e substitua o `feeds.opml`. Use só sites sem
  paywall e confira se o domínio está em `FULL_TEXT_DOMAINS` (`config.py`). Fora dessa
  lista, a matéria entra só com o título e o resumo do RSS.
- **Ritmo e tom da voz:** o estilo pedido ao Gemini fica em `TTS_STYLE` (conversa) e em
  `HEADLINE_TTS_STYLE` (manchetes da escalada, lidas com mais ênfase). Se mudar o estilo
  ou a voz, ajuste `WORDS_PER_MINUTE`; senão o episódio sai mais curto ou mais longo que
  o previsto.
- **Regras editoriais (o que entra e o que não entra):** `api/episode/prompts.py`.
- **Dólar usado para mostrar os custos em reais:** `BRL_PER_USD` (fixo) no `config.py`.

Para rodar localmente sem enviar, a partir da pasta `backend/`, com ffmpeg instalado e as
chaves no `.env`:

```
uv run python manage.py news_podcast --no-send
```

O áudio e os JSON da seleção e do roteiro ficam em `backend/news_podcast_output/`, que
está no `.gitignore`.

## Bom saber

- Os logs do Actions de um repositório público são públicos. Eles mostram as manchetes
  escolhidas, nunca as chaves, que o GitHub mascara.
- O GitHub pausa agendamentos em repositório público que fica 60 dias sem nenhuma
  atividade.
- O custo no log é o do plano pago; no plano grátis, a execução não custa nada. Os preços
  do Gemini em `PRICES` são promocionais até 31/12/2026 e dobram em 1/1/2027. Se o
  Google mudar a tabela, é só atualizar ali.
- O GitHub não garante o horário dos agendamentos: em momentos de carga ele atrasa ou até
  descarta execuções. Se a das 6h10 atrasar, o episódio sai assim que ficar pronto; se
  for descartada, o dia fica sem episódio (dá para rodar na mão em *Run workflow*).
- Se o Gemini 3.8 Flash estiver sobrecarregado, o texto é feito com o Gemini 3.6 Flash,
  e o resto da execução já vai direto para ele.
- A voz não tem reserva: se o Gemini estiver fora do ar, o código espera 10 minutos e
  depois 20 e tenta de novo. Se ainda falhar, ou se a cota do dia acabar, o episódio do
  dia não sai e chega uma mensagem de erro no Telegram.
