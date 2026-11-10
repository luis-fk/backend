import type { Locale } from "@/app/i18n";

// The plants texts: the login page and the chat. The project's name and the
// session messages are in the common dictionary. English has Portuguese's type,
// so a missing text fails the build.
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
  chat: {
    title: "Chat",
    greeting: "Olá! Como posso ajudar você hoje?",
    conversation: "Conversa",
    loadingHistory: "Carregando o histórico…",
    historyFailed: "Não foi possível carregar o histórico de mensagens.",
    messageLabel: "Mensagem",
    messagePlaceholder: "Escreva sua mensagem",
    send: "Enviar",
    sendFailed: "Falha ao enviar a mensagem. Tente de novo.",
  },
};

export type PlantsDictionary = typeof ptBR;

const en: PlantsDictionary = {
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
  chat: {
    title: "Chat",
    greeting: "Hi! How can I help you today?",
    conversation: "Conversation",
    loadingHistory: "Loading the history…",
    historyFailed: "Couldn't load the message history.",
    messageLabel: "Message",
    messagePlaceholder: "Write your message",
    send: "Send",
    sendFailed: "Failed to send the message. Try again.",
  },
};

export const plantsDictionary: Record<Locale, PlantsDictionary> = {
  "pt-BR": ptBR,
  en,
};
