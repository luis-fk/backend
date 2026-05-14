"use server";
import { createSession } from "@/app/actions/session";
import axios from "axios";

export async function login(
  formData: FormData,
): Promise<{ message: string } | undefined> {
  const name = formData.get("name");
  const serverUrl = process.env.NEXT_PUBLIC_SERVER_URL;

  if (!name || typeof name !== "string" || !name.trim()) {
    return { message: "Name is required." };
  }

  try {
    console.log(`[cfflch] Logging in as ${name}`);
    const result = await axios.get(`${serverUrl}/api/cfflch/users/${name}`);
    await createSession(result.data.id as number);
    return;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 404) {
        console.error(`[cfflch] User ${name} not found`);
        return {
          message:
            error.response.data?.error ?? "User not found.",
        };
      }
      console.error(`[cfflch] Login error for user ${name}`);
      return {
        message:
          error.response?.data?.error ?? "An error occurred. Please try again.",
      };
    }
    console.error(`[cfflch] Unknown login error for user ${name}`);
    return { message: "An unknown error occurred." };
  }
}