import { useEffect, useEffectEvent } from "react";
import { logger } from "@/app/api/log/client-logger";

// How an upload ended, sent once the backend has read the PDF.
export type UploadResult =
  | { upload_id: string; status: "ready"; text_id: number }
  | { upload_id: string; status: "failed"; reason: "no_text" | "error" };

interface UseTextsSocketProps {
  userId: number | undefined;
  token: string | undefined;
  serverUrl: string | undefined;
  onResult: (result: UploadResult) => void;
  onError: () => void;
}

// Connects on mount, so the socket is open before any upload: the backend does
// not re-deliver a result.
export function useTextsSocket({
  userId,
  token,
  serverUrl,
  onResult,
  onError,
}: UseTextsSocketProps): void {
  // Effect events read the latest callbacks without reconnecting the socket,
  // which would lose a result sent in between.
  const handleResult = useEffectEvent(onResult);
  const handleError = useEffectEvent(onError);

  useEffect(() => {
    if (!userId || !token || !serverUrl) return;

    const wsProtocol = serverUrl.startsWith("https://") ? "wss://" : "ws://";
    const wsUrl = `${wsProtocol}${serverUrl.split("://")[1]}/ws/political-culture/texts/${userId}`;
    // A browser can't set headers on a WebSocket, so the token goes as a
    // subprotocol (in the URL it would end up in access logs).
    const socket = new WebSocket(wsUrl, ["bearer", token]);

    socket.onmessage = (event: MessageEvent<string>) => {
      try {
        handleResult(JSON.parse(event.data) as UploadResult);
      } catch (error) {
        logger.error("Failed to parse a texts socket message", {
          data: event.data,
          error,
        });
      }
    };
    socket.onerror = (error: Event) => {
      logger.error("Texts socket error", { userId, error });
      handleError();
    };

    return () => socket.close();
  }, [userId, token, serverUrl]);
}
