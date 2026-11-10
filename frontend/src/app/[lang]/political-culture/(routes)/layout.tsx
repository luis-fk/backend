import AppHeader from "@/app/components/AppHeader";
import { localePath, toLocale } from "@/app/i18n";
import { politicalCultureDictionary } from "@/political-culture/dictionary";

export default async function RoutesLayout({
  children,
  params,
}: Readonly<{
  children: React.ReactNode;
  params: Promise<{ lang: string }>;
}>): Promise<React.ReactElement> {
  const lang = toLocale((await params).lang);
  const t = politicalCultureDictionary[lang].tabs;
  const links = [
    { href: localePath(lang, "/political-culture/chat"), label: t.chat },
    { href: localePath(lang, "/political-culture/texts"), label: t.texts },
  ];

  return (
    <div className="app-shell" data-project="political-culture">
      <AppHeader project="political-culture" links={links} />
      {children}
    </div>
  );
}
