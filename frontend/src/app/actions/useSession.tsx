// useSession.ts
import { getSession } from "@/actions/session";
import { JWTPayload } from "jose";
import { useState, useEffect } from "react";

export function useSession() {
  const [session, setSession] = useState<JWTPayload | undefined>(undefined);

  useEffect(() => {
    async function fetchSession() {
      const sessionData = await getSession();
      setSession(sessionData);
    }

    fetchSession();
  }, []);

  return session;
}
