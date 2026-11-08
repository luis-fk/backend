// The projects shown on the home page and in the project switcher.
// A new project needs an entry here, its accent in globals.css and its routes in proxy.ts.

export type ProjectKey = "plants" | "political-culture" | "cfflch";

export type Project = {
  key: ProjectKey;
  name: string;
  description: string;
  href: string;
};

export const PROJECTS: readonly Project[] = [
  {
    key: "plants",
    name: "Plantas",
    description:
      "Converse sobre a sua planta com os dados do sensor e do clima.",
    href: "/plants",
  },
  {
    key: "political-culture",
    name: "Cultura Política",
    description: "Tire dúvidas sobre política com um assistente.",
    href: "/political-culture",
  },
  {
    key: "cfflch",
    name: "CFFLCH",
    description: "Veja quais alunos aparecem nas listas de aprovados.",
    href: "/cfflch",
  },
];
