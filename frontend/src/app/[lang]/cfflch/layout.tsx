import type { Metadata } from "next";
import { commonDictionary } from "@/app/dictionary";
import { toLocale } from "@/app/i18n";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  const name =
    commonDictionary[toLocale((await params).lang)].projects.cfflch.name;
  return { title: { default: name, template: `%s | ${name}` } };
}

export default function CfflchLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): React.ReactElement {
  return <>{children}</>;
}
