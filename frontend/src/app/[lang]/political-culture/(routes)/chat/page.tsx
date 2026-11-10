import Chat from "@/political-culture/components/Chat";
import type { Metadata } from "next";
import { toLocale } from "@/app/i18n";
import { politicalCultureDictionary } from "@/political-culture/dictionary";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  const lang = toLocale((await params).lang);
  return { title: politicalCultureDictionary[lang].chat.title };
}

export default function Page(): React.ReactElement {
  return <Chat />;
}
