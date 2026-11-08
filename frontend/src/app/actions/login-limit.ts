import "server-only";
import { headers } from "next/headers";

// Login attempt limit: 5 wrong names from the same visitor within an hour block
// that visitor for an hour. Kept in memory, which is enough for the single
// Railway instance; the counts reset on each deploy. A plain server module, not
// a "use server" file, so these functions can't be called from outside.

const MAX_FAILURES = 5;
const HOUR_MS = 60 * 60 * 1000;

type Entry = { failures: number; firstFailureAt: number; blockedUntil: number };

const entries = new Map<string, Entry>();

// Drops the entries whose hour and block are both over.
function prune(now: number): void {
  for (const [ip, entry] of entries) {
    if (entry.firstFailureAt + HOUR_MS <= now && entry.blockedUntil <= now) {
      entries.delete(ip);
    }
  }
}

// The visitor's IP, as Railway's edge sends it. Without either header, every
// attempt shares the "unknown" count.
export async function visitorIp(): Promise<string> {
  const requestHeaders = await headers();
  return (
    requestHeaders.get("x-real-ip") ||
    requestHeaders.get("x-forwarded-for")?.split(",")[0].trim() ||
    "unknown"
  );
}

export function isBlocked(ip: string): boolean {
  const now = Date.now();
  prune(now);
  return (entries.get(ip)?.blockedUntil ?? 0) > now;
}

// Called before the lookup, so parallel attempts can't get past the limit:
// each one counts until undoFailure takes it back.
export function recordFailure(ip: string): void {
  const now = Date.now();
  prune(now);
  const entry = entries.get(ip) ?? {
    failures: 0,
    firstFailureAt: now,
    blockedUntil: 0,
  };
  entry.failures += 1;
  if (entry.failures >= MAX_FAILURES) entry.blockedUntil = now + HOUR_MS;
  entries.set(ip, entry);
}

// Takes back an attempt that wasn't a wrong name: the name was found, or the
// backend failed. Only time clears the wrong names, so logging in with a known
// name can't reset the limit.
export function undoFailure(ip: string): void {
  const entry = entries.get(ip);
  if (!entry) return;
  entry.failures -= 1;
  if (entry.failures < MAX_FAILURES) entry.blockedUntil = 0;
  if (entry.failures <= 0) entries.delete(ip);
}
