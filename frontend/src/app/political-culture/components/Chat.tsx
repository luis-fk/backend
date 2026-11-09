"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import axios from "axios";
import { useSession } from "@/app/actions/useSession";
import { useChatSocket } from "@/political-culture/hooks/useChatSocket";
import { logger } from "@/app/api/log/client-logger";
import Toast from "@/app/components/Toast";
import "@/political-culture/css/chat.css";

// The backend answers 401 once the session's token has expired (or the secrets
// changed); only a reload, which leads to the login page, fixes it.
const SESSION_EXPIRED = "Sua sessão expirou. Recarregue a página.";

function expired(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 401;
}

export interface MessageType {
  message: string;
  role: "human" | "ai";
}

export default function Chat(): React.ReactElement {
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
  const token = session?.token;
  const serverUrl = process.env.NEXT_PUBLIC_SERVER_URL;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    // loadingHistory starts as true, so there is nothing to set until the session arrives.
    if (!userId || !token || !serverUrl) return;

    const controller = new AbortController();
    axios
      .get<MessageType[]>(
        `${serverUrl}/api/political-culture/chat-history/${userId}`,
        {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        },
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
        setErrorMessage(
          expired(err)
            ? SESSION_EXPIRED
            : "Não foi possível carregar o histórico de mensagens.",
        );
      })
      .finally(() => {
        // Ignore runs that were cleaned up.
        if (!controller.signal.aborted) setLoadingHistory(false);
      });

    return () => controller.abort();
  }, [userId, token, serverUrl]);

  const handleNewMessage = useCallback((message: MessageType): void => {
    setMessages((previous) => [...previous, message]);
  }, []);

  const handleSocketError = useCallback((): void => {
    setErrorMessage("Conexão perdida. Tente recarregar a página.");
  }, []);

  useChatSocket({
    userId: userId?.toString(),
    token,
    serverUrl,
    onMessage: handleNewMessage,
    setSending,
    onError: handleSocketError,
  });

  const handleInputChange = (
    event: React.ChangeEvent<HTMLTextAreaElement>,
  ): void => {
    setInput(event.target.value);
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = "auto";
      ta.style.height = `${ta.scrollHeight}px`;
    }
  };

  const send = useCallback(async (): Promise<void> => {
    if (sending || !input.trim()) return;
    // No token yet, or no session (the chat shows the session error).
    if (!token) return;
    setSending(true);
    const userMsg = input.trim();
    setMessages((m) => [...m, { message: userMsg, role: "human" }]);
    setInput("");
    // The text is gone, so the textarea goes back to a single line.
    if (textareaRef.current) textareaRef.current.style.height = "";

    try {
      await axios.post(
        `${serverUrl}/api/political-culture/chatbot/message`,
        { user_id: userId, text: userMsg },
        { headers: { Authorization: `Bearer ${token}` } },
      );
    } catch (error) {
      logger.error("Failed to send chat message", {
        userId,
        error,
      });
      setErrorMessage(
        expired(error)
          ? SESSION_EXPIRED
          : "Falha ao enviar a mensagem. Tente de novo.",
      );
      setSending(false);
    }
  }, [sending, input, serverUrl, userId, token]);

  return (
    <main className="political-chat">
      <div className="political-chat-log">
        <div
          className="political-chat-column political-chat-messages"
          role="log"
          aria-label="Conversa"
        >
          {session === null ? (
            <p className="muted">
              Não foi possível carregar a sua sessão. Recarregue a página.
            </p>
          ) : loadingHistory ? (
            <p className="muted">Carregando o histórico…</p>
          ) : (
            messages.map((msg, i) =>
              // The user's own text is shown as typed; only answers are markdown.
              msg.role === "human" ? (
                <p key={i} className="political-chat-message" data-role="human">
                  {msg.message}
                </p>
              ) : (
                <div
                  key={i}
                  className="political-chat-message"
                  data-role={msg.role}
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    // No images: loading one could send data from the reply to
                    // any site its URL points to.
                    disallowedElements={["pre", "code", "img"]}
                    unwrapDisallowed={true}
                  >
                    {msg.message}
                  </ReactMarkdown>
                </div>
              ),
            )
          )}
        </div>
        {/* Outside the column, so the gap between messages does not add space at the end. */}
        <div ref={bottomRef} />
      </div>

      <div className="political-chat-column political-chat-footer">
        <div className="political-chat-composer">
          <label htmlFor="chat-message" className="visually-hidden">
            Mensagem
          </label>
          <textarea
            ref={textareaRef}
            id="chat-message"
            className="political-chat-input"
            value={input}
            placeholder="Escreva sua mensagem"
            rows={1}
            onChange={handleInputChange}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                send();
              }
            }}
          />
          <button
            type="button"
            className="political-chat-send"
            onClick={send}
            disabled={sending}
            aria-label="Enviar"
          >
            <svg
              aria-hidden="true"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 19V5" />
              <path d="M5 12l7-7 7 7" />
            </svg>
          </button>
        </div>
      </div>

      <Toast message={errorMessage} onClose={() => setErrorMessage(null)} />
    </main>
  );
}
