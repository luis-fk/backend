import type { Metadata } from "next";
import { connection } from "next/server";
import SearchForm from "@/cfflch/components/search-form";

export const metadata: Metadata = {
  title: "Buscar alunos",
};

// The year list ends at the current year, so the page renders on each request:
// prerendered, it would keep the build's year and fail hydration in a new year.
export default async function SearchPage(): Promise<React.ReactElement> {
  await connection();
  return <SearchForm />;
}
