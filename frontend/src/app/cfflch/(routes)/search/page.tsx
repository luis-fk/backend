import type { Metadata } from "next";
import SearchForm from "@/cfflch/components/search-form";

export const metadata: Metadata = {
  title: "Buscar alunos",
};

export default function SearchPage(): React.ReactElement {
  return <SearchForm />;
}
