import { getSession } from "@/app/actions/session";
import { logger } from "@/app/api/log/client-logger";
import { useState, useEffect } from "react";

// token goes with every call to the backend: "Authorization: Bearer <token>",
// or the WebSocket subprotocols ["bearer", token].
type Session = { userId: number; token: string };

// undefined while loading, null when there is no valid session.
export function useSession(appName: string): Session | null | undefined {
  const [session, setSession] = useState<Session | null | undefined>(undefined);

  useEffect(() => {
    async function fetchSession() {
      try {
        setSession(await getSession(appName));
      } catch (error) {
        logger.error("Failed to load session", { appName, error });
        setSession(null);
      }
    }

    fetchSession();
  }, [appName]);

  return session;
}
