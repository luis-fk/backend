import type { Metadata } from "next";

export const metadata: Metadata = {
  title: { default: "Cultura Política", template: "%s | Cultura Política" },
};

export default function PoliticalCultureLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): React.ReactElement {
  return <>{children}</>;
}
