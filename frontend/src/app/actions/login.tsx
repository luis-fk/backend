"use server";
import { createSession } from "./session";

import axios from "axios";

export async function login(formData: FormData) {
  const name = formData.get("name");

  const serverUrl = process.env.NEXT_PUBLIC_SERVER_URL;

  try {
    console.log(`Logging in as ${name}`);

    const result = await axios.get(`${serverUrl}/api/user/${name}`);
    await createSession(result.data.id as number);

    return;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 404) {
        console.error(`User ${name} not found on the server`);

        return { message: error.response.data.error };
      }
      console.error(
        `An error ocurred when making the API call for user ${name}`,
      );

      return { message: error.response?.data || "An error occurred" };
    }
    console.error(
      `An unknown error occurred when making the API call for user ${name}`,
    );

    return { message: "An unknown error occurred" };
  }
}
