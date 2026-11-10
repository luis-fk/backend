import "server-only";
import { JWTPayload, SignJWT, jwtVerify } from "jose";
import { cookies } from "next/headers";

// The session: a JWT (HS256, 7 days) with the user id and the app, kept in the
// httpOnly cookie "session-<app>". A plain server module, not a "use server" file,
// so these functions can't be called from outside: a callable createSession would
// log anyone in as any user.

// Read when used, so a missing or short secret fails loudly instead of signing
// with an empty key: a session that verifies gets an API token (getSession).
function sessionKey(): Uint8Array {
  const secret = process.env.SESSION_SECRET;
  if (!secret || secret.length < 32) {
    throw new Error(
      "SESSION_SECRET must have at least 32 characters (see README.md).",
    );
  }
  return new TextEncoder().encode(secret);
}

async function encrypt(userId: number, app: string): Promise<string> {
  console.log(`Encrypting session for user ${userId}`);

  const payload: JWTPayload = { userId, app };
  return new SignJWT(payload)
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("7d")
    .sign(sessionKey());
}

// The session's payload, when it is valid and belongs to the app. Without the
// app check, a session cookie copied from another app would work there too.
export async function decrypt(
  session: string | undefined,
  app: string,
): Promise<JWTPayload | undefined> {
  console.log("Decrypting session");

  try {
    const { payload } = await jwtVerify(session ?? "", sessionKey(), {
      algorithms: ["HS256"],
    });
    if (payload.app === app) return payload;
  } catch (error) {
    console.error(
      "Failed to verify session",
      error instanceof Error ? error.message : "",
    );
  }
}

export async function createSession(
  userId: number,
  app: string,
): Promise<void> {
  console.log(`Creating session for user ${userId} (${app})`);

  const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
  const session = await encrypt(userId, app);
  const cookieStore = await cookies();

  cookieStore.set(`session-${app}`, session, {
    httpOnly: true,
    secure: true,
    expires: expiresAt,
    sameSite: "lax",
    path: "/",
  });
}

export async function deleteSession(app: string): Promise<void> {
  console.log(`Deleting session (${app})`);

  // Without a path, delete uses "/", the path createSession sets.
  const cookieStore = await cookies();
  cookieStore.delete(`session-${app}`);
}
