"use server";
import { createSession } from "@/app/actions/session";
import axios from "axios";

export async function login(
  formData: FormData,
): Promise<{ message: string } | undefined> {
  const name = formData.get("name");
  const serverUrl = process.env.NEXT_PUBLIC_SERVER_URL;

  if (!name || typeof name !== "string" || !name.trim()) {
    return { message: "Digite seu nome." };
  }

  try {
    console.log(`[cfflch] Logging in as ${name}`);
    const result = await axios.get(`${serverUrl}/api/cfflch/users/${name}`);
    await createSession(result.data.id as number, "session-cfflch");
    return;
  } catch (error) {
    // The backend's messages are in English, so the page uses its own.
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      console.error(`[cfflch] User ${name} not found`);
      return { message: "Nome não encontrado." };
    }
    console.error(`[cfflch] Login error for user ${name}`);
    return { message: "Não foi possível entrar. Tente de novo." };
  }
}
