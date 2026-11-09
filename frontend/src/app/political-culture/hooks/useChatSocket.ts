import { useEffect, useCallback } from "react";
import { logger } from "@/app/api/log/client-logger";
import { MessageType } from "@/political-culture/components/Chat";

interface UseChatSocketProps {
  userId: string | undefined;
  token: string | undefined;
  serverUrl: string | undefined;
  onMessage: (message: MessageType) => void;
  onFailedAnswer: () => void;
  setSending: (sending: boolean) => void;
  onError: () => void;
}

export function useChatSocket({
  userId,
  token,
  serverUrl,
  onMessage,
  onFailedAnswer,
  setSending,
  onError,
}: UseChatSocketProps) {
  const handleOpen = useCallback(() => {
    logger.log("WebSocket connection established", { userId });
  }, [userId]);

  const handleMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        if (data.message && data.role) {
          onMessage(data);
        } else if (data.failed) {
          onFailedAnswer();
        }
      } catch (e) {
        logger.error("Failed to parse WebSocket message", {
          data: event.data,
          error: e,
        });
      } finally {
        setSending(false);
      }
    },
    [onMessage, onFailedAnswer, setSending],
  );

  const handleError = useCallback(
    (error: Event) => {
      logger.error("WebSocket error", { userId, error });
      setSending(false);
      onError();
    },
    [userId, setSending, onError],
  );

  const handleClose = useCallback(() => {
    logger.log("WebSocket connection closed", { userId });
  }, [userId]);

  useEffect(() => {
    if (!userId || !token || !serverUrl) return;

    const wsProtocol = serverUrl.startsWith("https://") ? "wss://" : "ws://";
    const wsUrl = `${wsProtocol}${serverUrl.split("://")[1]}/ws/chat/${userId}`;
    // A browser can't set headers on a WebSocket, so the token goes as a
    // subprotocol (in the URL it would end up in access logs).
    const socket = new WebSocket(wsUrl, ["bearer", token]);

    socket.onopen = handleOpen;
    socket.onmessage = handleMessage;
    socket.onerror = handleError;
    socket.onclose = handleClose;

    return () => socket.close();
  }, [
    userId,
    token,
    serverUrl,
    handleOpen,
    handleMessage,
    handleError,
    handleClose,
  ]);
}
