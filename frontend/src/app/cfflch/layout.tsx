import type { Metadata } from "next";

export const metadata: Metadata = {
  title: { default: "CFFLCH", template: "%s | CFFLCH" },
};

export default function CfflchLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): React.ReactElement {
  return <>{children}</>;
}
