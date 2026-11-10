import AppHeader from "@/app/components/AppHeader";
import { localePath, toLocale } from "@/app/i18n";

export default async function RoutesLayout({
  children,
  params,
}: Readonly<{
  children: React.ReactNode;
  params: Promise<{ lang: string }>;
}>): Promise<React.ReactElement> {
  const lang = toLocale((await params).lang);
  const links = [
    { href: localePath(lang, "/cfflch/search"), label: "Buscar" },
    { href: localePath(lang, "/cfflch/results"), label: "Resultados" },
  ];

  return (
    <div className="app-shell" data-project="cfflch">
      <AppHeader project="cfflch" links={links} />
      {children}
    </div>
  );
}
