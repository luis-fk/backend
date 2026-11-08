import "server-only";
import { SignJWT } from "jose";

// Tokens for the Django API: HS256 JWTs signed with API_TOKEN_SECRET, which the
// backend shares. A plain server module, not a "use server" file, so these
// functions can't be called from outside.

function secretKey(): Uint8Array {
  const secret = process.env.API_TOKEN_SECRET;
  // jose would sign with an empty key, and the backend would refuse every call.
  if (!secret) throw new Error("API_TOKEN_SECRET is not set (see README.md).");
  return new TextEncoder().encode(secret);
}

// Sent by the browser on every call. It expires with the session (exp in seconds).
export function createUserToken(
  app: string,
  userId: number,
  exp: number,
): Promise<string> {
  return new SignJWT({ app, purpose: "user" })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(String(userId))
    .setIssuedAt()
    .setExpirationTime(exp)
    .sign(secretKey());
}

// Sent by a login Server Action with the user lookup. It lasts a minute.
export function createLoginToken(app: string): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  return new SignJWT({ app, purpose: "login" })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt(now)
    .setExpirationTime(now + 60)
    .sign(secretKey());
}
