import type { Metadata } from "next";

import "@/plants/css/layout.css";

export const metadata: Metadata = {
  title: "Plants",
};

export default function PlantsLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <>{children}</>;
}
