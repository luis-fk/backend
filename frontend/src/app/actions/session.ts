"use server";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { createUserToken } from "@/app/actions/api-token";
import { decrypt, deleteSession } from "@/app/actions/session-cookie";
import { isLocale, localePath } from "@/app/i18n";
import { PROJECTS } from "@/app/projects";

// Every export of a "use server" file is a Server Action, which anyone can call
// with a POST request. These two only read or end the caller's own session;
// creating one lives in session-cookie.ts, which can't be called from outside.

// The user id and the API token, or null without a valid session.
export async function getSession(
  app: string,
): Promise<{ userId: number; token: string } | null> {
  console.log(`Getting session (${app})`);

  const cookieStore = await cookies();
  const payload = await decrypt(cookieStore.get(`session-${app}`)?.value, app);
  if (typeof payload?.userId !== "number" || !payload.exp) return null;

  const token = await createUserToken(app, payload.userId, payload.exp);
  return { userId: payload.userId, token };
}

// Ends the app's session and goes back to its login page, in the same language.
// Both values go into the redirect, so only known ones are accepted.
export async function logout(lang: string, app: string): Promise<void> {
  if (!isLocale(lang) || !PROJECTS.some((project) => project.key === app)) {
    return;
  }

  await deleteSession(app);
  redirect(localePath(lang, `/${app}`));
}
