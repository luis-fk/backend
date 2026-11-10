import type { Metadata } from "next";
import { connection } from "next/server";
import { toLocale } from "@/app/i18n";
import SearchForm from "@/cfflch/components/search-form";
import { cfflchDictionary } from "@/cfflch/dictionary";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  return {
    title: cfflchDictionary[toLocale((await params).lang)].search.title,
  };
}

// The year list ends at the current year, so the page renders on each request:
// prerendered, it would keep the build's year and fail hydration in a new year.
export default async function SearchPage(): Promise<React.ReactElement> {
  await connection();
  return <SearchForm />;
}
