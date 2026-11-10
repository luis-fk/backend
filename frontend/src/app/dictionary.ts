import type { Locale } from "@/app/i18n";
import type { ProjectKey } from "@/app/projects";

// The texts every app shares: the home, the 404, the header, the theme switch,
// the toast and the session messages. Each app keeps its own texts in its
// dictionary.ts. English has Portuguese's type, so a missing text fails the
// build.
const ptBR = {
  title: "Projetos",
  home: {
    title: "Projetos",
    projectsNav: "Projetos",
  },
  projects: {
    plants: {
      name: "Plantas",
      description:
        "Converse sobre a sua planta com os dados do sensor e do clima.",
    },
    "political-culture": {
      name: "Cultura Política",
      description: "Tire dúvidas sobre política com um assistente.",
    },
    cfflch: {
      name: "CFFLCH",
      description: "Veja quais alunos aparecem nas listas de aprovados.",
    },
  } satisfies Record<ProjectKey, { name: string; description: string }>,
  header: {
    switchProject: (name: string): string => `${name}, trocar de projeto`,
    projectsNav: "Projetos",
    allProjects: "Todos os projetos",
    logout: "Sair",
  },
  theme: {
    dark: "Modo escuro",
  },
  toast: {
    close: "Fechar aviso",
  },
  notFound: {
    title: "Página não encontrada",
    text: "Este endereço não existe ou mudou.",
    back: "Voltar para os projetos",
  },
  session: {
    loadFailed: "Não foi possível carregar a sua sessão. Recarregue a página.",
    expired: "Sua sessão expirou. Recarregue a página.",
  },
};

export type CommonDictionary = typeof ptBR;

const en: CommonDictionary = {
  title: "Projects",
  home: {
    title: "Projects",
    projectsNav: "Projects",
  },
  projects: {
    plants: {
      name: "Plants",
      description: "Talk about your plant with its sensor and weather data.",
    },
    "political-culture": {
      name: "Political Culture",
      description: "Ask an assistant your questions about politics.",
    },
    cfflch: {
      name: "CFFLCH",
      description: "See which students appear on the admission lists.",
    },
  },
  header: {
    switchProject: (name) => `${name}, switch project`,
    projectsNav: "Projects",
    allProjects: "All projects",
    logout: "Sign out",
  },
  theme: {
    dark: "Dark mode",
  },
  toast: {
    close: "Close notice",
  },
  notFound: {
    title: "Page not found",
    text: "This address doesn't exist or has changed.",
    back: "Back to projects",
  },
  session: {
    loadFailed: "Couldn't load your session. Reload the page.",
    expired: "Your session has expired. Reload the page.",
  },
};

export const commonDictionary: Record<Locale, CommonDictionary> = {
  "pt-BR": ptBR,
  en,
};
