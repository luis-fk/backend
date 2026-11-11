import type { Locale } from "@/app/i18n";

// The plants texts: the login page, the chat and the sensors tab. The project's name and the
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
  tabs: { chat: "Chat", sensors: "Sensores" },
  sensors: {
    title: "Sensores",
    plant: "Planta",
    period: "Período",
    periods: { 24: "24 h", 168: "7 dias", 720: "30 dias" },
    measuresLabel: "Medidas",
    measures: {
      soil: "Umidade do solo (%)",
      air: "Umidade do ar (%)",
      temp: "Temperatura (°C)",
    },
    lastReading: (when: string): string => `Última leitura, ${when}:`,
    soil: "solo",
    air: "ar",
    rawReading: (raw: string): string => `(leitura ${raw})`,
    humidityPanel: "Umidade (%)",
    temperaturePanel: "Temperatura (°C)",
    hourTick: (date: Date): string => `${date.getHours()}h`,
    loading: "Carregando as leituras…",
    noDevices: "Nenhum sensor na sua conta ainda.",
    noReadings: "Sem leituras neste período.",
    pickOne: "Escolha pelo menos uma medida.",
    noData: "Sem dados neste período.",
    loadFailed: "Não foi possível carregar as leituras.",
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
  tabs: { chat: "Chat", sensors: "Sensors" },
  sensors: {
    title: "Sensors",
    plant: "Plant",
    period: "Period",
    periods: { 24: "24 h", 168: "7 days", 720: "30 days" },
    measuresLabel: "Measures",
    measures: {
      soil: "Soil moisture (%)",
      air: "Air humidity (%)",
      temp: "Temperature (°C)",
    },
    lastReading: (when: string): string => `Last reading, ${when}:`,
    soil: "soil",
    air: "air",
    rawReading: (raw: string): string => `(reading ${raw})`,
    humidityPanel: "Humidity (%)",
    temperaturePanel: "Temperature (°C)",
    hourTick: (date: Date): string =>
      date.toLocaleTimeString("en", { hour: "numeric" }),
    loading: "Loading the readings…",
    noDevices: "No sensors on your account yet.",
    noReadings: "No readings in this period.",
    pickOne: "Pick at least one measure.",
    noData: "No data in this period.",
    loadFailed: "Couldn't load the readings.",
  },
};

export const plantsDictionary: Record<Locale, PlantsDictionary> = {
  "pt-BR": ptBR,
  en,
};
