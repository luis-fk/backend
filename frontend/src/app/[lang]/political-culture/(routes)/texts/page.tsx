import Texts from "@/political-culture/components/Texts";
import type { Metadata } from "next";
import { toLocale } from "@/app/i18n";
import { politicalCultureDictionary } from "@/political-culture/dictionary";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  const lang = toLocale((await params).lang);
  return { title: politicalCultureDictionary[lang].texts.title };
}

export default function Page(): React.ReactElement {
  return <Texts />;
}
