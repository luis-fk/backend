"use server";
import { createLoginToken } from "@/app/actions/api-token";
import {
  isBlocked,
  recordFailure,
  undoFailure,
  visitorIp,
} from "@/app/actions/login-limit";
import { createSession } from "@/app/actions/session-cookie";
import { DEFAULT_LOCALE, isLocale } from "@/app/i18n";
import { cfflchDictionary } from "@/cfflch/dictionary";
import axios from "axios";

export async function login(
  lang: string,
  formData: FormData,
): Promise<{ message: string } | undefined> {
  // Anyone can call a Server Action with any language, so an unknown one
  // answers in Portuguese.
  const t = cfflchDictionary[isLocale(lang) ? lang : DEFAULT_LOCALE].login;
  const name = formData.get("name");
  const serverUrl = process.env.NEXT_PUBLIC_SERVER_URL;

  if (!name || typeof name !== "string" || !name.trim()) {
    return { message: t.emptyName };
  }

  const ip = await visitorIp();
  if (isBlocked(ip)) {
    console.warn(`[cfflch] Too many wrong names from ${ip}`);
    return { message: t.tooManyAttempts };
  }
  // Counted up front, so parallel attempts can't get past the limit.
  recordFailure(ip);

  try {
    console.log(`[cfflch] Logging in as ${name}`);
    const token = await createLoginToken("cfflch");
    const result = await axios.get(
      `${serverUrl}/api/cfflch/users/${encodeURIComponent(name.trim())}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    undoFailure(ip);
    await createSession(result.data.id as number, "cfflch");
    return;
  } catch (error) {
    // The backend's messages are in English, so the page uses its own.
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      console.error(`[cfflch] User ${name} not found (${ip})`);
      return { message: t.nameNotFound };
    }
    // Only wrong names count.
    undoFailure(ip);
    console.error(`[cfflch] Login error for user ${name}`);
    return { message: t.failed };
  }
}
