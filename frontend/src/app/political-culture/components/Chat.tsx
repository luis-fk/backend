"use client";

import { useEffect, useState, useRef, useCallback, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import axios from "axios";
import { useMediaQuery } from "@mui/material";
import { useSession } from "@/app/actions/useSession";
import { useChatSocket } from "@/political-culture/hooks/useChatSocket";
import { logger } from "@/app/api/log/client-logger";
import Toast from "@/app/components/Toast";
import "@/political-culture/css/chat.css";

export interface MessageType {
  message: string;
  role: "human" | "ai";
}

export default function Chat() {
  const [messages, setMessages] = useState<MessageType[]>([
    {
      message: "Olá! Como posso ajudar você hoje?",
      role: "ai",
    },
  ]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const session = useSession("political-culture");
  const userId = session?.userId;
  const serverUrl = process.env.NEXT_PUBLIC_SERVER_URL;

  // MUI returns false until hydration ends, so no isClient flag is needed.
  const isMobile = useMediaQuery("(max-width: 800px)");

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    // loadingHistory starts as true, so there is nothing to set until the session arrives.
    if (!userId || !serverUrl) return;

    const controller = new AbortController();
    axios
      .get<MessageType[]>(
        `${serverUrl}/api/political-culture/chat-history/${userId}`,
        { signal: controller.signal },
      )
      .then((res) => {
        if (res.status === 200 && res.data.length > 0) {
          setMessages(res.data);
        }
      })
      .catch((err: unknown) => {
        if (axios.isCancel(err)) return;
        logger.error("Failed to fetch chat history", {
          userId,
          error: err,
        });
        setErrorMessage("Não foi possível carregar o histórico de mensagens.");
      })
      .finally(() => {
        // Ignore runs that were cleaned up.
        if (!controller.signal.aborted) setLoadingHistory(false);
      });

    return () => controller.abort();
  }, [userId, serverUrl]);

  const handleNewMessage = useCallback((message: MessageType) => {
    setMessages((previous) => [...previous, message]);
  }, []);

  const handleSocketError = useCallback(() => {
    setErrorMessage("Conexão perdida. Tente recarregar a página.");
  }, []);

  useChatSocket({
    userId: userId?.toString(),
    serverUrl,
    onMessage: handleNewMessage,
    setSending,
    onError: handleSocketError,
  });

  const handleInputChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(event.target.value);
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = "auto";
      ta.style.height = `${ta.scrollHeight}px`;
    }
  };

  const send = useCallback(async () => {
    if (sending || !input.trim()) return;
    setSending(true);
    const userMsg = input.trim();
    setMessages((m) => [...m, { message: userMsg, role: "human" }]);
    setInput("");

    try {
      await axios.post(`${serverUrl}/api/political-culture/chatbot/message`, {
        user_id: userId,
        text: userMsg,
      });
    } catch (error) {
      logger.error("Failed to send chat message", {
        userId,
        error,
      });
      setErrorMessage("Falha ao enviar a mensagem. Tente novamente.");
      setSending(false);
    }
  }, [sending, input, serverUrl, userId]);

  const containerStyle = useMemo(
    () => ({
      width: isMobile ? "90vw" : "60vw",
      height: isMobile ? "85vh" : "95vh",
    }),
    [isMobile],
  );

  return (
    <div className="chat-container" style={containerStyle}>
      <div className="message-list">
        {session === null ? (
          <div className="loading-history">
            Não foi possível carregar a sua sessão. Recarregue a página.
          </div>
        ) : loadingHistory ? (
          <div className="loading-history">Loading chat history...</div>
        ) : (
          messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              <div className="bubble">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  disallowedElements={["pre", "code"]}
                  unwrapDisallowed={true}
                >
                  {msg.message}
                </ReactMarkdown>
              </div>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
      <div className="input-area">
        <textarea
          ref={textareaRef}
          className="chat-input"
          value={input}
          disabled={sending}
          placeholder="Escreva sua mensagem…"
          rows={1}
          onChange={handleInputChange}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              send();
            }
          }}
        />
        <button onClick={send} disabled={sending}>
          Enviar
        </button>
      </div>

      <Toast message={errorMessage} onClose={() => setErrorMessage(null)} />
    </div>
  );
}