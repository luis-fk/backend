import type { Metadata } from "next";
import { connection } from "next/server";
import ResultsTable from "@/cfflch/components/results-table";

export const metadata: Metadata = {
  title: "Resultados",
};

// The year list ends at the current year, so the page renders on each request:
// prerendered, it would keep the build's year and fail hydration in a new year.
export default async function ResultsPage(): Promise<React.ReactElement> {
  await connection();
  return <ResultsTable serverUrl={process.env.NEXT_PUBLIC_SERVER_URL} />;
}
