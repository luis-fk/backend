import type { Metadata } from "next";
import ResultsTable from "@/cfflch/components/results-table";

export const metadata: Metadata = {
  title: "CFFLCH — Results",
};

export default function ResultsPage(): React.ReactElement {
  return <ResultsTable serverUrl={process.env.NEXT_PUBLIC_SERVER_URL} />;
}