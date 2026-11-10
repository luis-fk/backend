import AppHeader from "@/app/components/AppHeader";
import { localePath, toLocale } from "@/app/i18n";
import { cfflchDictionary } from "@/cfflch/dictionary";

export default async function RoutesLayout({
  children,
  params,
}: Readonly<{
  children: React.ReactNode;
  params: Promise<{ lang: string }>;
}>): Promise<React.ReactElement> {
  const lang = toLocale((await params).lang);
  const t = cfflchDictionary[lang].tabs;
  const links = [
    { href: localePath(lang, "/cfflch/search"), label: t.search },
    { href: localePath(lang, "/cfflch/results"), label: t.results },
  ];

  return (
    <div className="app-shell" data-project="cfflch">
      <AppHeader project="cfflch" links={links} />
      {children}
    </div>
  );
}
