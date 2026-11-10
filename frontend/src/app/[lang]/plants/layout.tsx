import type { Metadata } from "next";
import { commonDictionary } from "@/app/dictionary";
import { toLocale } from "@/app/i18n";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  const lang = toLocale((await params).lang);
  const name = commonDictionary[lang].projects.plants.name;
  return { title: { default: name, template: `%s | ${name}` } };
}

export default function PlantsLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): React.ReactElement {
  return <>{children}</>;
}
