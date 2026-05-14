import { getSession } from "@/app/actions/session";
import { useState, useEffect } from "react";

type Session = { userId: number };

export function useSession(appName: string) {
  const [session, setSession] = useState<Session | undefined>(undefined);

  useEffect(() => {
    async function fetchSession() {
      const sessionData = await getSession(`session-${appName}`);
      if (sessionData && typeof sessionData.userId === "number") {
        setSession({ userId: sessionData.userId });
      }
    }

    fetchSession();
  }, [appName]);

  return session;
}
