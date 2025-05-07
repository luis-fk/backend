import type { Metadata } from "next";

import "@/app/main-page.css";

export const metadata: Metadata = {
  title: "Felipe's Projects",
};

export default function RootLayout({
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
