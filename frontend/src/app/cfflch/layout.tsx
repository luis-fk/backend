import type { Metadata } from "next";

import "@/cfflch/css/layout.css";

export const metadata: Metadata = {
  title: "CFFLCH",
};

export default function CfflchLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): React.ReactElement {
  return <>{children}</>;
}