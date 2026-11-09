import Texts from "@/political-culture/components/Texts";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Textos",
};

export default function Page(): React.ReactElement {
  return <Texts />;
}
