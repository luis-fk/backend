import type { Metadata } from "next";

import "@/plants/css/layout.css";

export const metadata: Metadata = {
  title: "Plants",
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
