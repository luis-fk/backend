import type { Metadata } from "next";

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
