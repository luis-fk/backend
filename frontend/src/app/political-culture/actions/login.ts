"use server";
import { createLoginToken } from "@/app/actions/api-token";
import {
  isBlocked,
  recordFailure,
  undoFailure,
  visitorIp,
} from "@/app/actions/login-limit";
import { createSession } from "@/app/actions/session-cookie";
import axios from "axios";

export async function login(
  formData: FormData,
): Promise<{ message: string } | undefined> {
  const name = formData.get("name");
  const serverUrl = process.env.NEXT_PUBLIC_SERVER_URL;

  if (!name || typeof name !== "string" || !name.trim()) {
    return { message: "Digite seu nome." };
  }

  const ip = await visitorIp();
  if (isBlocked(ip)) {
    console.warn(`[political-culture] Too many wrong names from ${ip}`);
    return { message: "Muitas tentativas. Tente de novo em até 1 hora." };
  }
  // Counted up front, so parallel attempts can't get past the limit.
  recordFailure(ip);

  try {
    console.log(`[political-culture] Logging in as ${name}`);
    const token = await createLoginToken("political-culture");
    const result = await axios.get(
      `${serverUrl}/api/political-culture/users/${encodeURIComponent(name.trim())}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    undoFailure(ip);
    await createSession(result.data.id as number, "political-culture");
    return;
  } catch (error) {
    // The backend's messages are in English, so the page uses its own.
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      console.error(`[political-culture] User ${name} not found (${ip})`);
      return { message: "Nome não encontrado." };
    }
    // Only wrong names count.
    undoFailure(ip);
    console.error(`[political-culture] Login error for user ${name}`);
    return { message: "Não foi possível entrar. Tente de novo." };
  }
}
