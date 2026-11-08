import AppHeader from "@/app/components/AppHeader";

const NAV_LINKS = [
  { href: "/cfflch/search", label: "Buscar" },
  { href: "/cfflch/results", label: "Resultados" },
];

export default function RoutesLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): React.ReactElement {
  return (
    <div className="app-shell" data-project="cfflch">
      <AppHeader project="cfflch" links={NAV_LINKS} />
      {children}
    </div>
  );
}
