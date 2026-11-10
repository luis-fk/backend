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
    { href: localePath(lang, "/political-culture/chat"), label: "Chat" },
    { href: localePath(lang, "/political-culture/texts"), label: "Textos" },
  ];

  return (
    <div className="app-shell" data-project="political-culture">
      <AppHeader project="political-culture" links={links} />
      {children}
    </div>
  );
}
