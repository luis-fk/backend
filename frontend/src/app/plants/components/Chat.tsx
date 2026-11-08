"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import axios from "axios";
import { useSession } from "@/app/actions/useSession";
import { logger } from "@/app/api/log/client-logger";
import Toast from "@/app/components/Toast";
import "@/plants/css/chat.css";

export interface MessageType {
  message: string;
  role: string;
}

// POST /api/chatbot/message answers with { user_id, response: { role, message } }.
interface ChatbotResponse {
  response: MessageType;
}

const GREETING: MessageType = {
  message: "Olá! Como posso ajudar você hoje?",
  role: "ai",
};

export default function Chat(): React.ReactElement {
  const [messages, setMessages] = useState<MessageType[]>([GREETING]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [sending, setSending] = useState(false);
  const [messageInput, setMessageInput] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const session = useSession("plants");
  const userId = session?.userId;
  const serverUrl = process.env.NEXT_PUBLIC_SERVER_URL;

  // Without a session (null) there is no history to wait for.
  const showLoading = loadingHistory && session !== null;

  useEffect(() => {
    // loadingHistory starts as true, so there is nothing to set until the session arrives.
    if (!userId) return;

    async function fetchChatHistory(): Promise<void> {
      try {
        const response = await axios.get<MessageType[]>(
          `${serverUrl}/api/chat-history/${userId}`,
        );

        // A 204, or a 200 with an empty list, means there is no history yet.
        if (response.status === 200 && response.data.length > 0) {
          setMessages(response.data);
        } else {
          setMessages([GREETING]);
        }
      } catch (error: unknown) {
        logger.error("Failed to fetch chat history", { userId, error });
        setErrorMessage("Não foi possível carregar o histórico de mensagens.");
      } finally {
        setLoadingHistory(false);
      }
    }

    fetchChatHistory();
  }, [userId, serverUrl]);

  // Keep the latest message in view, also when the history replaces the loading
  // text. A layout effect runs before the browser paints, so a long history
  // never flashes at the top before the jump.
  useLayoutEffect(() => {
    const list = scrollRef.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [messages, showLoading]);

  async function handleSendMessage(): Promise<void> {
    const userMessage = messageInput.trim();

    // One message at a time: send only after the assistant has answered.
    if (!userMessage || messages[messages.length - 1]?.role !== "ai") return;

    setSending(true);
    setMessages((previous) => [
      ...previous,
      { message: userMessage, role: "human" },
    ]);
    setMessageInput("");
    // The text is gone, so the textarea goes back to a single line.
    if (textareaRef.current) textareaRef.current.style.height = "";

    try {
      const response = await axios.post<ChatbotResponse>(
        `${serverUrl}/api/chatbot/message`,
        { user_id: userId, message: userMessage },
      );

      setMessages((previous) => [
        ...previous,
        { message: response.data.response.message, role: "ai" },
      ]);
    } catch (error: unknown) {
      logger.error("Failed to send chat message", { userId, error });
      // Take the message back into the input, so the last message is the
      // assistant's again and the user can retry.
      setMessages((previous) => previous.slice(0, -1));
      setMessageInput((current) => current || userMessage);
      setErrorMessage("Falha ao enviar a mensagem. Tente de novo.");
    } finally {
      setSending(false);
    }
  }

  function handleInputChange(
    event: React.ChangeEvent<HTMLTextAreaElement>,
  ): void {
    setMessageInput(event.target.value);
    // Grow with the text; the CSS max-height stops it at about six lines.
    const textarea = event.target;
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  }

  function handleKeyDown(
    event: React.KeyboardEvent<HTMLTextAreaElement>,
  ): void {
    // Enter sends and Shift+Enter breaks the line.
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    handleSendMessage();
  }

  return (
    <main className="plants-chat">
      <div ref={scrollRef} className="plants-chat-scroll">
        <div
          className="plants-chat-column plants-chat-messages"
          role="log"
          aria-label="Conversa"
        >
          {session === null ? (
            <p className="muted">
              Não foi possível carregar a sua sessão. Recarregue a página.
            </p>
          ) : showLoading ? (
            <p className="muted">Carregando o histórico…</p>
          ) : (
            messages.map((msg, index) =>
              msg.role === "human" ? (
                <p key={index} className="plants-chat-user">
                  {msg.message}
                </p>
              ) : (
                <div key={index} className="plants-chat-assistant">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    disallowedElements={["pre", "code"]}
                    unwrapDisallowed={true}
                  >
                    {msg.message}
                  </ReactMarkdown>
                </div>
              ),
            )
          )}
        </div>
      </div>

      <div className="plants-chat-column plants-chat-footer">
        <form className="plants-chat-composer" onSubmit={handleSubmit}>
          <label htmlFor="plants-chat-message" className="visually-hidden">
            Mensagem
          </label>
          <textarea
            id="plants-chat-message"
            ref={textareaRef}
            className="plants-chat-input"
            rows={1}
            value={messageInput}
            placeholder="Escreva sua mensagem"
            enterKeyHint="send"
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
          />
          <button
            type="submit"
            className="plants-chat-send"
            aria-label="Enviar"
            disabled={sending}
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
        </form>
      </div>

      <Toast message={errorMessage} onClose={() => setErrorMessage(null)} />
    </main>
  );
}
