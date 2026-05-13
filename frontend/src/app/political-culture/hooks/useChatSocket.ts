import { useEffect, useCallback } from "react";
import { logger } from "@/app/api/log/client-logger";
import { MessageType } from "@/political-culture/components/Chat";

interface UseChatSocketProps {
  userId: string | undefined;
  serverUrl: string | undefined;
  onMessage: (message: MessageType) => void;
  setSending: (sending: boolean) => void;
  onError: () => void;
}

export function useChatSocket({
  userId,
  serverUrl,
  onMessage,
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
    [onMessage, setSending],
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
    if (!userId || !serverUrl) return;

    const wsProtocol = serverUrl.startsWith("https://") ? "wss://" : "ws://";
    const wsUrl = `${wsProtocol}${serverUrl.split("://")[1]}/ws/chat/${userId}`;
    const socket = new WebSocket(wsUrl);

    socket.onopen = handleOpen;
    socket.onmessage = handleMessage;
    socket.onerror = handleError;
    socket.onclose = handleClose;

    return () => socket.close();
  }, [userId, serverUrl, handleOpen, handleMessage, handleError, handleClose]);
}