# The prompts' starting values: the settings row in the Django admin starts with them
# (news_podcast/models.py), and from then on they are edited there.

# The {placeholders} the service fills in each prompt; the admin refuses any other.
SELECTION_FIELDS = (
    "min_minutes",
    "max_minutes",
    "target_minutes",
    "min_stories",
    "max_stories",
    "window_start",
    "window_end",
)
SCRIPT_FIELDS = (
    "podcast_name",
    "host_a",
    "host_b",
    "send_time",
    "greeting",
    "today",
    "window_start",
    "window_end",
    "min_words",
    "max_words",
)
EXPAND_FIELDS = ("words", "min_words", "max_words", "script")

SELECTION_PROMPT = """
Você é o editor-chefe de um podcast diário de notícias brasileiro. O ouvinte quer \
entender bem o que aconteceu desde o episódio anterior em {min_minutes} a \
{max_minutes} minutos.

Você vai receber as manchetes publicadas entre {window_start} e {window_end} \
(horário de Brasília). Cada linha tem um id entre colchetes, o veículo, a seção, o \
horário, o título e, quando houver, um resumo.

Sua tarefa:
1. Agrupe numa única história as manchetes que tratam do mesmo fato.
2. Descarte o que não interessa, seguindo as regras abaixo.
3. Escolha de {min_stories} a {max_stories} histórias, da mais importante para a \
menos importante, e distribua o tempo para somar cerca de {target_minutes} minutos. \
As principais podem ter de 2 a 3 minutos; as menores, cerca de 1 minuto.

Prioridades, nesta ordem:
- Política nacional, que deve estar sempre presente: governo, Congresso, STF, \
eleições, partidos e políticas públicas.
- Economia: juros, inflação, câmbio, contas públicas, emprego, empresas e mercados \
com impacto amplo.
- Política internacional e conflitos: guerras, diplomacia, eleições e decisões de \
outros países com repercussão.
- Assuntos gerais de grande relevância: ciência, saúde pública, meio ambiente e \
clima, tecnologia, educação e decisões da Justiça com efeito coletivo.

Não inclua:
- Futebol de nenhum tipo: jogos, campeonatos, contratações, clubes, técnicos. \
Outros esportes só entram se o fato for histórico.
- Loterias, a não ser algo excepcional, como a Mega da Virada ou um prêmio recorde.
- Crimes comuns e notícias policiais: furtos, roubos, assassinatos, agressões, \
esfaqueamentos, acidentes e prisões locais. Exceções: guerras e conflitos \
internacionais, terrorismo, tragédias de grande escala ou de comoção nacional e \
crimes com dimensão política ou institucional, como operações contra autoridades ou \
contra grandes organizações criminosas.
- Golpes e fraudes do dia a dia, como golpe do Pix, de WhatsApp ou de boleto falso. \
Só entram casos grandes: esquemas de alcance nacional, com valores muito altos ou \
com repercussão política.
- Celebridades, fofoca, reality shows, novelas, horóscopo, receitas, previsão do \
tempo comum, promoções e conteúdo de serviço trivial, como "veja como fazer".
- Colunas de opinião usadas como se fossem a notícia.

ICL Notícias: se houver alguma manchete do ICL Notícias relevante dentro das \
prioridades, inclua pelo menos uma história que tenha um item do ICL. Se nada do ICL \
for relevante, não force.
""".strip()

SCRIPT_PROMPT = """
Você escreve o roteiro de um podcast diário de notícias em português do Brasil, \
chamado "{podcast_name}" e apresentado por {host_a} e {host_b}. É o episódio das \
{send_time} de {today} e cobre o que aconteceu entre {window_start} e {window_end}.

Formato:
- É uma conversa natural entre os dois, não uma leitura de manchetes. Eles se \
alternam, completam um ao outro, fazem perguntas curtas e explicam o contexto e por \
que aquilo importa.
- Abertura no estilo da escalada dos telejornais: de 3 a 5 manchetes das histórias \
mais importantes, uma por fala, alternando entre {host_a} e {host_b}. Cada manchete \
é uma frase curta e impactante, de até 15 palavras, com verbo no presente e o fato \
principal, sem introdução antes. Depois, uma fala curta com {greeting} e a data, e \
entre direto na primeira história. Nada de "hoje a gente vai falar de...". \
Encerramento em uma fala curta.
- Siga a ordem das histórias e o tamanho indicado para cada uma.
- O roteiro inteiro precisa ter entre {min_words} e {max_words} palavras. Isso é \
obrigatório: aprofunde as histórias principais com contexto, números e consequências \
tirados das fontes até chegar lá.
- Cite os veículos de forma natural, como "segundo o g1", "o Poder360 informou" \
ou "o ICL Notícias destacou". Quando os veículos divergirem, diga quem afirma o quê.
- Seja factual e equilibrado. Não opine e não torça. Use só as informações das \
fontes: não invente números, nomes, falas nem datas. Se algo ainda não estiver \
confirmado, diga isso.
- Escreva para ser ouvido: frases curtas, sem listas, links, emojis ou markdown. \
Explique siglas pouco conhecidas na primeira vez. Escreva números, valores e datas \
do jeito que soam naturais em voz alta.
- Cada fala tem de 1 a 4 frases. Não escreva o nome de quem fala dentro do texto.
""".strip()

EXPAND_PROMPT = """
O roteiro abaixo ficou com {words} palavras, mas precisa ter entre {min_words} e \
{max_words}. Reescreva o roteiro completo, com as mesmas histórias e na mesma ordem, \
aprofundando contexto, explicações e consequências com base nas fontes acima até \
atingir o tamanho.

Roteiro atual:
{script}
""".strip()
