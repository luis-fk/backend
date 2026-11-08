import type { Metadata } from "next";
import { PROJECTS } from "@/app/projects";

export const metadata: Metadata = {
  title: PROJECTS.find((project) => project.key === "political-culture")?.name,
};

export default function PoliticalCultureLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): React.ReactElement {
  return <>{children}</>;
}
