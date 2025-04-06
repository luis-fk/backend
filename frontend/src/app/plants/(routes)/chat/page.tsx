import Chat from "@/app/plants/components/Chat";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Chat",
};

export default function Page() {
  return <Chat />;
}
