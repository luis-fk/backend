import type { Metadata, Viewport } from "next";
import { Schibsted_Grotesk } from "next/font/google";

import "@/app/globals.css";

const sans = Schibsted_Grotesk({
  subsets: ["latin", "latin-ext"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Projetos",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#141618" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): React.ReactElement {
  return (
    <html lang="pt-BR" className={sans.variable}>
      <body>{children}</body>
    </html>
  );
}
