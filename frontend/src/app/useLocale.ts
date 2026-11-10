import { useParams } from "next/navigation";
import { DEFAULT_LOCALE, type Locale, isLocale } from "@/app/i18n";

// The page's language, from the [lang] segment of its path; Portuguese when the
// route has no [lang] param, so a 404 never throws again.
export function useLocale(): Locale {
  const { lang } = useParams<{ lang?: string }>();
  return lang && isLocale(lang) ? lang : DEFAULT_LOCALE;
}
