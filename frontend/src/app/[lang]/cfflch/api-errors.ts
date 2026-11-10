import axios from "axios";
import { commonDictionary } from "@/app/dictionary";
import type { Locale } from "@/app/i18n";

// The message for a failed call to the backend. The backend answers 401 once
// the session's token has expired (or the secrets changed); only a reload,
// which leads to the login page, fixes it.
export function errorMessage(
  lang: Locale,
  error: unknown,
  fallback: string,
): string {
  return axios.isAxiosError(error) && error.response?.status === 401
    ? commonDictionary[lang].session.expired
    : fallback;
}
