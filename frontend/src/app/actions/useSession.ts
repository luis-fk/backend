import { getSession } from "@/app/actions/session";
import { logger } from "@/app/api/log/client-logger";
import { useState, useEffect } from "react";

type Session = { userId: number };

// undefined while loading, null when there is no valid session.
export function useSession(appName: string): Session | null | undefined {
  const [session, setSession] = useState<Session | null | undefined>(
    undefined,
  );

  useEffect(() => {
    async function fetchSession() {
      try {
        const sessionData = await getSession(`session-${appName}`);
        setSession(
          sessionData && typeof sessionData.userId === "number"
            ? { userId: sessionData.userId }
            : null,
        );
      } catch (error) {
        logger.error("Failed to load session", { appName, error });
        setSession(null);
      }
    }

    fetchSession();
  }, [appName]);

  return session;
}
