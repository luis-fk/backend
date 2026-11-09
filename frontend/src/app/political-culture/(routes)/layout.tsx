import AppHeader from "@/app/components/AppHeader";

const NAV_LINKS = [
  { href: "/political-culture/chat", label: "Chat" },
  { href: "/political-culture/texts", label: "Textos" },
];

export default function RoutesLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): React.ReactElement {
  return (
    <div className="app-shell" data-project="political-culture">
      <AppHeader project="political-culture" links={NAV_LINKS} />
      {children}
    </div>
  );
}
