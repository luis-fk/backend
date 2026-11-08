import type { Metadata } from "next";
import { Schibsted_Grotesk } from "next/font/google";
import { cookies } from "next/headers";

import "@/app/globals.css";

const sans = Schibsted_Grotesk({
  subsets: ["latin", "latin-ext"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Projetos",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): Promise<React.ReactElement> {
  // Saved by ThemeToggle. Reading it here sends each page already in the chosen
  // theme, so nothing flashes on load; without it, the CSS follows the system.
  const saved = (await cookies()).get("theme")?.value;
  const theme = saved === "light" || saved === "dark" ? saved : undefined;

  return (
    <html lang="pt-BR" className={sans.variable} data-theme={theme}>
      <body>{children}</body>
    </html>
  );
}
