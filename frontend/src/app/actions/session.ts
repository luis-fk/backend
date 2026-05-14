"use server";
import { JWTPayload, SignJWT, jwtVerify } from "jose";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

const secretKey = process.env.SESSION_SECRET;
const encodedKey = new TextEncoder().encode(secretKey);

export async function encrypt(userId: number) {
  console.log(`Encrypting session for user ${userId}`);

  const payload: JWTPayload = { userId: userId };
  return new SignJWT(payload)
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("7d")
    .sign(encodedKey);
}

export async function getSession(cookieName: string) {
  console.log(`Getting session from cookies (${cookieName})`);

  const cookieStore = await cookies();
  const session = cookieStore.get(cookieName)?.value;
  const payload = await decrypt(session);

  return payload;
}

export async function decrypt(session: string | undefined = "") {
  console.log("Decrypting session");

  try {
    const { payload } = await jwtVerify(session, encodedKey, {
      algorithms: ["HS256"],
    });
    return payload;
  } catch {
    console.error("Failed to verify session");
  }
}

export async function createSession(userId: number, cookieName: string) {
  console.log(`Creating session for user ${userId} (${cookieName})`);

  const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
  const session = await encrypt(userId);
  const cookieStore = await cookies();

  cookieStore.set(cookieName, session, {
    httpOnly: true,
    secure: true,
    expires: expiresAt,
    sameSite: "lax",
    path: "/",
  });
}

export async function updateSession(cookieName: string) {
  console.log(`Updating session (${cookieName})`);

  const session = (await cookies()).get(cookieName)?.value;
  const payload = await decrypt(session);

  if (!session || !payload) {
    return null;
  }

  const expires = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);

  const cookieStore = await cookies();
  cookieStore.set(cookieName, session, {
    httpOnly: true,
    secure: true,
    expires: expires,
    sameSite: "lax",
    path: "/",
  });
}

export const verifySession = cache(
  async (cookieName: string, appName: string) => {
    console.log(`Verifying session (${cookieName})`);

    const cookie = (await cookies()).get(cookieName)?.value;
    const session = await decrypt(cookie);

    if (!session?.userId) {
      redirect(`/${appName}`);
    }

    return { isAuth: true, userId: session.userId };
  },
);

export async function deleteSession(cookieName: string) {
  console.log(`Deleting session (${cookieName})`);

  const cookieStore = await cookies();
  cookieStore.delete(cookieName);
}
