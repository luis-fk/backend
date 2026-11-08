import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Plantas",
};

export default function PlantsLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): React.ReactElement {
  return <>{children}</>;
}
