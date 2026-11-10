"use server";

import { cookies } from "next/headers";

const ONE_YEAR_IN_SECONDS = 60 * 60 * 24 * 365;

// Saved by the server, not with document.cookie: Safari deletes cookies that
// JavaScript writes after 7 days without a visit. The root layout's script reads
// it on each page load, so it can't be httpOnly.
export async function saveTheme(theme: "light" | "dark"): Promise<void> {
  // Anyone can call a Server Action with any value.
  if (theme !== "light" && theme !== "dark") return;
  (await cookies()).set("theme", theme, {
    maxAge: ONE_YEAR_IN_SECONDS,
    sameSite: "lax",
    httpOnly: false,
  });
}
