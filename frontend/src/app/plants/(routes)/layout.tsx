import AppHeader from "@/app/components/AppHeader";

export default function RoutesLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): React.ReactElement {
  return (
    <div className="app-shell" data-project="plants">
      <AppHeader project="plants" />
      {children}
    </div>
  );
}
