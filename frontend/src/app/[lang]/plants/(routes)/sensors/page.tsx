import Sensors from "@/plants/components/Sensors";
import type { Metadata } from "next";
import { plantsDictionary } from "@/plants/dictionary";
import { toLocale } from "@/app/i18n";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  return {
    title: plantsDictionary[toLocale((await params).lang)].sensors.title,
  };
}

export default function Page(): React.ReactElement {
  return <Sensors />;
}
