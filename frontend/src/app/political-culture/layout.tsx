import type { Metadata } from "next";

import "@/political-culture/css/layout.css";

export const metadata: Metadata = {
  title: "Cultura Política",
};

export default function PoliticalCultureLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <>{children}</>;
}
