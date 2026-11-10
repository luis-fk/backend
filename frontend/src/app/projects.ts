// The projects shown on the home page and in the project switcher; their names
// and descriptions are in the common dictionary (dictionary.ts). A new project
// needs an entry here and there, its accent in globals.css and its routes in
// proxy.ts.

export type ProjectKey = "plants" | "political-culture" | "cfflch";

export type Project = {
  key: ProjectKey;
  // Without the language: localePath adds it.
  path: string;
};

export const PROJECTS: readonly Project[] = [
  { key: "plants", path: "/plants" },
  { key: "political-culture", path: "/political-culture" },
  { key: "cfflch", path: "/cfflch" },
];
