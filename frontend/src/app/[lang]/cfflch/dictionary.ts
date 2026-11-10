import type { Locale } from "@/app/i18n";

// The cfflch texts; the project's name and the session messages are in the
// common dictionary. English has Portuguese's type, so a missing text fails the
// build.
const ptBR = {
  tabs: {
    search: "Buscar",
    results: "Resultados",
  },
  login: {
    title: "Entrar",
    intro: "Use o nome que foi cadastrado para você.",
    nameLabel: "Seu nome",
    namePlaceholder: "Maria Souza",
    submit: "Entrar",
    submitting: "Entrando…",
    back: "Voltar para os projetos",
    emptyName: "Digite seu nome.",
    tooManyAttempts: "Muitas tentativas. Tente de novo em até 1 hora.",
    nameNotFound: "Nome não encontrado.",
    failed: "Não foi possível entrar. Tente de novo.",
  },
  search: {
    title: "Buscar alunos",
    intro: "Procuramos cada nome nas listas de aprovados publicadas em PDF.",
    namesLabel: "Nomes, um por linha",
    namesPlaceholder: "João Silva\nMaria Souza",
    yearLabel: "Ano",
    classLabel: "Turma (opcional)",
    classPlaceholder: "Turma A",
    submit: "Buscar",
    submitting: "Buscando…",
    resultsTitle: "Resultado da busca",
    notOnAnyList: "Não aparece em nenhuma lista",
    onOneList: "Aparece em 1 lista",
    // The count comes already formatted for the language.
    onLists: (count: string): string => `Aparece em ${count} listas`,
    failed: "A busca falhou. Tente de novo.",
    searching: "Buscando nas listas…",
    done: "Busca concluída.",
    connectError:
      "Não foi possível conectar ao servidor. Recarregue a página e tente de novo.",
    startError: "Não foi possível iniciar a busca. Tente de novo.",
  },
  results: {
    title: "Resultados",
    // The words after each count in the summary ("3 alunos, 2 aprovados"),
    // in the plural that fits the count.
    summary: {
      students: (count: number): string => (count === 1 ? "aluno" : "alunos"),
      approved: (count: number): string =>
        count === 1 ? "aprovado" : "aprovados",
    },
    yearLabel: "Ano",
    listsLabel: "Listas",
    pdfFilters: {
      all: "Todos",
      found: "Com PDF",
      "not-found": "Sem PDF",
    },
    classLabel: "Turma",
    allClasses: "Todas as turmas",
    loading: "Carregando resultados…",
    failed: (year: number): string =>
      `Não foi possível carregar os resultados de ${year}.`,
    empty: (year: number): string => `Nenhum resultado para ${year}.`,
    noMatches: "Nenhum resultado com esses filtros.",
    classesError: "Não foi possível carregar as turmas. Tente de novo.",
    resultsError: "Não foi possível carregar os resultados. Tente de novo.",
  },
  resultCard: {
    notOnAnyList: "Não aparece em nenhuma lista",
    approved: "Aprovado",
    classOf: (name: string): string => `Turma de ${name}`,
    noClass: "Sem turma",
    delete: "Excluir",
    deleteLabel: (name: string): string => `Excluir ${name}`,
    confirmDelete: (name: string): string => `Excluir o resultado de ${name}?`,
    approvalError: "Não foi possível atualizar a aprovação. Tente de novo.",
    classError: "Não foi possível mudar a turma. Tente de novo.",
    deleteError: "Não foi possível excluir o resultado. Tente de novo.",
  },
};

export type CfflchDictionary = typeof ptBR;

const en: CfflchDictionary = {
  tabs: {
    search: "Search",
    results: "Results",
  },
  login: {
    title: "Sign in",
    intro: "Use the name that was registered for you.",
    nameLabel: "Your name",
    namePlaceholder: "Maria Souza",
    submit: "Sign in",
    submitting: "Signing in…",
    back: "Back to projects",
    emptyName: "Enter your name.",
    tooManyAttempts: "Too many attempts. Try again in an hour.",
    nameNotFound: "Name not found.",
    failed: "Couldn't sign in. Try again.",
  },
  search: {
    title: "Search students",
    intro: "We look for each name on the admission lists published as PDFs.",
    namesLabel: "Names, one per line",
    namesPlaceholder: "João Silva\nMaria Souza",
    yearLabel: "Year",
    classLabel: "Class (optional)",
    classPlaceholder: "Class A",
    submit: "Search",
    submitting: "Searching…",
    resultsTitle: "Search results",
    notOnAnyList: "Doesn't appear on any list",
    onOneList: "Appears on 1 list",
    onLists: (count) => `Appears on ${count} lists`,
    failed: "The search failed. Try again.",
    searching: "Searching the lists…",
    done: "Search complete.",
    connectError:
      "Couldn't connect to the server. Reload the page and try again.",
    startError: "Couldn't start the search. Try again.",
  },
  results: {
    title: "Results",
    summary: {
      students: (count) => (count === 1 ? "student" : "students"),
      approved: () => "approved",
    },
    yearLabel: "Year",
    listsLabel: "Lists",
    pdfFilters: {
      all: "All",
      found: "With PDF",
      "not-found": "Without PDF",
    },
    classLabel: "Class",
    allClasses: "All classes",
    loading: "Loading results…",
    failed: (year) => `Couldn't load the results for ${year}.`,
    empty: (year) => `No results for ${year}.`,
    noMatches: "No results match these filters.",
    classesError: "Couldn't load the classes. Try again.",
    resultsError: "Couldn't load the results. Try again.",
  },
  resultCard: {
    notOnAnyList: "Doesn't appear on any list",
    approved: "Approved",
    classOf: (name) => `${name}'s class`,
    noClass: "No class",
    delete: "Delete",
    deleteLabel: (name) => `Delete ${name}`,
    confirmDelete: (name) => `Delete the result for ${name}?`,
    approvalError: "Couldn't update the approval. Try again.",
    classError: "Couldn't change the class. Try again.",
    deleteError: "Couldn't delete the result. Try again.",
  },
};

export const cfflchDictionary: Record<Locale, CfflchDictionary> = {
  "pt-BR": ptBR,
  en,
};
