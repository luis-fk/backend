import { createSession } from "./session";

import axios from "axios";

export async function login(formData: FormData) {
  const name = formData.get("name");

  const serverUrl = process.env.NEXT_PUBLIC_SERVER_URL;

  try {
    const result = await axios.get(`${serverUrl}/api/user/${name}`);
    await createSession(result.data.id as number);

    return;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 404) {
        return { message: error.response.data.error };
      }
      return { message: error.response?.data || "An error occurred" };
    }
    return { message: "An unknown error occurred" };
  }
}
