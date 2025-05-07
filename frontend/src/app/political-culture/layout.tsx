import type { Metadata } from "next";

import "@/political-culture/css/layout.css";

export const metadata: Metadata = {
  title: "Political Culture",
};

export default function PoliticalCultureLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
