import AppHeader from "@/app/components/AppHeader";
import { localePath, toLocale } from "@/app/i18n";
import { plantsDictionary } from "@/plants/dictionary";

export default async function RoutesLayout({
  children,
  params,
}: Readonly<{
  children: React.ReactNode;
  params: Promise<{ lang: string }>;
}>): Promise<React.ReactElement> {
  const lang = toLocale((await params).lang);
  const t = plantsDictionary[lang].tabs;
  const links = [
    { href: localePath(lang, "/plants/chat"), label: t.chat },
    { href: localePath(lang, "/plants/sensors"), label: t.sensors },
  ];

  return (
    <div className="app-shell" data-project="plants">
      <AppHeader project="plants" links={links} />
      {children}
    </div>
  );
}
