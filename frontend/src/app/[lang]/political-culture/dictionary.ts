import type { Locale } from "@/app/i18n";

// Political Culture's texts: the login, the chat and the library. The project's
// name and the session messages are in src/app/dictionary.ts. English has
// Portuguese's type, so a missing text fails the build.
const ptBR = {
  login: {
    title: "Entrar",
    intro: "Use o nome que foi cadastrado para você.",
    back: "Voltar para os projetos",
    nameLabel: "Seu nome",
    namePlaceholder: "Maria Souza",
    submit: "Entrar",
    submitting: "Entrando…",
    nameMissing: "Digite seu nome.",
    tooManyAttempts: "Muitas tentativas. Tente de novo em até 1 hora.",
    nameNotFound: "Nome não encontrado.",
    failed: "Não foi possível entrar. Tente de novo.",
  },
  tabs: {
    chat: "Chat",
    texts: "Textos",
  },
  chat: {
    title: "Chat",
    greeting: "Olá! Como posso ajudar você hoje?",
    conversation: "Conversa",
    loadingHistory: "Carregando o histórico…",
    messageLabel: "Mensagem",
    messagePlaceholder: "Escreva sua mensagem",
    send: "Enviar",
    historyFailed: "Não foi possível carregar o histórico de mensagens.",
    answerFailed: "Não foi possível responder à mensagem. Tente de novo.",
    connectionLost: "Conexão perdida. Tente recarregar a página.",
    sendFailed: "Falha ao enviar a mensagem. Tente de novo.",
  },
  texts: {
    title: "Textos",
    intro:
      "A biblioteca do assistente. Marque os textos que ele usa nas suas análises: cada pessoa escolhe os seus, e um texto novo começa desmarcado.",
    upload: {
      label: "PDF de até 100 MB",
      choose: "Escolher PDF",
      noFile: "Nenhum arquivo escolhido",
      submit: "Adicionar texto",
      socketClosed:
        "A conexão com o servidor caiu. Recarregue a página para adicionar textos.",
      sending: (name: string, percent: number): string =>
        `Enviando ${name}… ${percent}%`,
      sendingLabel: "Envio do PDF",
      processing: (name: string): string => `Processando ${name}…`,
      processingLabel: "Leitura do PDF",
      processingHint:
        "Um livro leva alguns minutos. Você pode sair desta página: o texto aparece na lista quando terminar.",
      invalidFile: "Escolha um PDF de até 100 MB.",
      failed: "Não foi possível enviar o PDF.",
      tooBig: "Envie um PDF de até 100 MB.",
      duplicate: "Este PDF já está na biblioteca, ou ainda está sendo lido.",
      retry: "Não foi possível enviar o PDF. Tente de novo.",
      ready: (name: string): string => `${name} entrou na biblioteca.`,
      noText: (name: string): string =>
        `Não há texto para ler em ${name}. Um PDF escaneado precisa passar por OCR antes.`,
      readFailed: (name: string): string =>
        `Não foi possível ler ${name}. Tente de novo.`,
      dropped: (name: string, sent: boolean): string =>
        `A conexão caiu durante ${sent ? "a leitura" : "o envio"} de ${name}. Recarregue a página: se a leitura terminar, o texto aparece na lista.`,
    },
    library: {
      title: "Biblioteca",
      summary: (selected: number, total: number): string =>
        `${selected} de ${total} ${total === 1 ? "texto" : "textos"} nas suas análises`,
      loadFailed: "Não foi possível carregar a biblioteca.",
      loading: "Carregando a biblioteca…",
      empty: "A biblioteca está vazia. Adicione o primeiro PDF.",
      untitled: "Sem título",
      unknownAuthor: "Autor desconhecido",
      // The count comes already formatted in the page's language.
      words: (count: string): string => `${count} palavras`,
      addedBy: (name: string): string => `adicionado por ${name}`,
      descriptionLabel: "Resumo",
      pick: "Usar nas minhas análises",
      untitledText: "texto sem título",
      saveFailed: "Não foi possível salvar a sua escolha. Tente de novo.",
    },
  },
};

export type PoliticalCultureDictionary = typeof ptBR;

const en: PoliticalCultureDictionary = {
  login: {
    title: "Sign in",
    intro: "Use the name that was registered for you.",
    back: "Back to projects",
    nameLabel: "Your name",
    namePlaceholder: "Maria Souza",
    submit: "Sign in",
    submitting: "Signing in…",
    nameMissing: "Enter your name.",
    tooManyAttempts: "Too many attempts. Try again in an hour.",
    nameNotFound: "Name not found.",
    failed: "Couldn't sign in. Try again.",
  },
  tabs: {
    chat: "Chat",
    texts: "Texts",
  },
  chat: {
    title: "Chat",
    greeting: "Hi! How can I help you today?",
    conversation: "Conversation",
    loadingHistory: "Loading the history…",
    messageLabel: "Message",
    messagePlaceholder: "Write your message",
    send: "Send",
    historyFailed: "Couldn't load the message history.",
    answerFailed: "Couldn't answer the message. Try again.",
    connectionLost: "Connection lost. Try reloading the page.",
    sendFailed: "Failed to send the message. Try again.",
  },
  texts: {
    title: "Texts",
    intro:
      "The assistant's library. Tick the texts it uses in your analyses: each person picks their own, and a new text starts unticked.",
    upload: {
      label: "PDF up to 100 MB",
      choose: "Choose PDF",
      noFile: "No file chosen",
      submit: "Add text",
      socketClosed:
        "The connection to the server dropped. Reload the page to add texts.",
      sending: (name, percent) => `Uploading ${name}… ${percent}%`,
      sendingLabel: "Uploading the PDF",
      processing: (name) => `Processing ${name}…`,
      processingLabel: "Reading the PDF",
      processingHint:
        "A book takes a few minutes. You can leave this page: the text appears in the list when it's done.",
      invalidFile: "Choose a PDF of up to 100 MB.",
      failed: "Couldn't upload the PDF.",
      tooBig: "Upload a PDF of up to 100 MB.",
      duplicate: "This PDF is already in the library, or is still being read.",
      retry: "Couldn't upload the PDF. Try again.",
      ready: (name) => `${name} was added to the library.`,
      noText: (name) =>
        `There's no text to read in ${name}. A scanned PDF needs to go through OCR first.`,
      readFailed: (name) => `Couldn't read ${name}. Try again.`,
      dropped: (name, sent) =>
        `The connection dropped while ${sent ? "reading" : "uploading"} ${name}. Reload the page: if the reading finishes, the text appears in the list.`,
    },
    library: {
      title: "Library",
      summary: (selected, total) =>
        `${selected} of ${total} ${total === 1 ? "text" : "texts"} in your analyses`,
      loadFailed: "Couldn't load the library.",
      loading: "Loading the library…",
      empty: "The library is empty. Add the first PDF.",
      untitled: "Untitled",
      unknownAuthor: "Unknown author",
      words: (count) => `${count} words`,
      addedBy: (name) => `added by ${name}`,
      descriptionLabel: "Summary",
      pick: "Use in my analyses",
      untitledText: "untitled text",
      saveFailed: "Couldn't save your choice. Try again.",
    },
  },
};

export const politicalCultureDictionary: Record<
  Locale,
  PoliticalCultureDictionary
> = {
  "pt-BR": ptBR,
  en,
};
