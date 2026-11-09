import { useEffect, useEffectEvent, useState } from "react";
import { logger } from "@/app/api/log/client-logger";

// How an upload ended, sent once the backend has read the PDF. upload_id is the
// one the page sent with the file.
export type UploadResult =
  | { upload_id: string; status: "ready"; text_id: number }
  | { upload_id: string; status: "failed"; reason: "no_text" | "error" };

export type SocketState = "connecting" | "open" | "closed";

interface UseTextsSocketProps {
  userId: number | undefined;
  token: string | undefined;
  serverUrl: string | undefined;
  onResult: (result: UploadResult) => void;
  onClose: () => void;
}

// Connects on mount: the backend does not re-deliver a result, so an upload must
// wait for "open". A closed socket stays closed (a backend deploy closes it) and
// the page asks for a reload, as the chat does.
export function useTextsSocket({
  userId,
  token,
  serverUrl,
  onResult,
  onClose,
}: UseTextsSocketProps): SocketState {
  const [state, setState] = useState<SocketState>("connecting");
  // Effect events read the latest callbacks without reconnecting the socket,
  // which would lose a result sent in between.
  const handleResult = useEffectEvent(onResult);
  const handleClose = useEffectEvent(onClose);

  useEffect(() => {
    if (!userId || !token || !serverUrl) return;

    const wsProtocol = serverUrl.startsWith("https://") ? "wss://" : "ws://";
    const wsUrl = `${wsProtocol}${serverUrl.split("://")[1]}/ws/political-culture/texts/${userId}`;
    // A browser can't set headers on a WebSocket, so the token goes as a
    // subprotocol (in the URL it would end up in access logs).
    const socket = new WebSocket(wsUrl, ["bearer", token]);

    socket.onopen = () => setState("open");
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
    };
    socket.onclose = () => {
      logger.log("Texts socket closed", { userId });
      setState("closed");
      handleClose();
    };

    return () => {
      // Closing on unmount or on a new token is not a dropped connection.
      socket.onclose = null;
      socket.close();
    };
  }, [userId, token, serverUrl]);

  return state;
}
