import Chat from "@/app/political-culture/components/Chat";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Chat",
};

export default function Page() {
  return <Chat />;
}
