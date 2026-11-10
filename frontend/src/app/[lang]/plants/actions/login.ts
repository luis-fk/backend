"use server";
import { createLoginToken } from "@/app/actions/api-token";
import {
  isBlocked,
  recordFailure,
  undoFailure,
  visitorIp,
} from "@/app/actions/login-limit";
import { createSession } from "@/app/actions/session-cookie";
import { plantsDictionary } from "@/plants/dictionary";
import { DEFAULT_LOCALE, isLocale } from "@/app/i18n";
import axios from "axios";

// Answers in the page's language. Anyone can call a Server Action, so an
// unknown language gets Portuguese.
export async function login(
  lang: string,
  formData: FormData,
): Promise<{ message: string } | undefined> {
  const t = plantsDictionary[isLocale(lang) ? lang : DEFAULT_LOCALE];
  const name = formData.get("name");
  const serverUrl = process.env.NEXT_PUBLIC_SERVER_URL;

  if (!name || typeof name !== "string" || !name.trim()) {
    return { message: t.login.nameMissing };
  }

  const ip = await visitorIp();
  if (isBlocked(ip)) {
    console.warn(`[plants] Too many wrong names from ${ip}`);
    return { message: t.login.tooManyAttempts };
  }
  // Counted up front, so parallel attempts can't get past the limit.
  recordFailure(ip);

  try {
    console.log(`[plants] Logging in as ${name}`);
    const token = await createLoginToken("plants");
    const result = await axios.get(
      `${serverUrl}/api/plants/users/${encodeURIComponent(name.trim())}/`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    undoFailure(ip);
    await createSession(result.data.id as number, "plants");
    return;
  } catch (error) {
    // The backend's messages are in English, so the page uses its own.
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      console.error(`[plants] User ${name} not found (${ip})`);
      return { message: t.login.nameNotFound };
    }
    // Only wrong names count.
    undoFailure(ip);
    console.error(`[plants] Login error for user ${name}`);
    return { message: t.login.failed };
  }
}
