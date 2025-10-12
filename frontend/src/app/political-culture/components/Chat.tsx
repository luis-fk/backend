"use client";

import { useEffect, useState, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import axios from "axios";
import { useSession } from "@/app/actions/useSession";
import { useMediaQuery } from "@mui/material";
import { logger } from "@/app/api/log/client-logger";
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
  const bottomRef = useRef<HTMLDivElement>(null);
  const [isClient, setIsClient] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const session = useSession();
  const serverUrl = process.env.NEXT_PUBLIC_SERVER_URL;

  const isMobile = useMediaQuery("(max-width: 800px)");

  useEffect(() => {
    setIsClient(true);
  }, []);

  useEffect(() => {
    const ta = textareaRef.current;

    if (!ta) {
      return;
    }

    ta.style.height = "auto";
    ta.style.height = ta.scrollHeight + "px";
  }, [input]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!session?.userId || !serverUrl) {
      setLoadingHistory(false);
      return;
    }

    axios
      .get(`${serverUrl}/api/political-culture/chat-history/${session.userId}`)
      .then((res) => {
        if (res.status === 200 && res.data.length > 0) {
          setMessages(res.data);
        }
      })
      .catch((err) => {
        logger.error("Failed to fetch chat history", {
          userId: session.userId,
          error: err,
        });
      })
      .finally(() => {
        setLoadingHistory(false);
      });

    const wsProtocol = serverUrl.startsWith("https://") ? "wss://" : "ws://";
    const wsUrl = `${wsProtocol}${serverUrl.split("://")[1]}/ws/chat/${
      session.userId
    }`;
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      logger.log("WebSocket connection established", {
        userId: session.userId,
      });
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.message && data.role) {
        setMessages((previous) => [...previous, data]);
      }
      setSending(false);
    };

    socket.onerror = (error) =>
      logger.error("WebSocket error", { userId: session.userId, error });

    socket.onclose = () => {
      logger.log("WebSocket connection closed", { userId: session.userId });
    };

    return () => socket.close();
  }, [session?.userId, serverUrl]);

  async function send() {
    if (sending || !input.trim()) return;
    setSending(true);
    const userMsg = input.trim();
    setMessages((m) => [...m, { message: userMsg, role: "human" }]);
    setInput("");

    try {
      await axios.post(`${serverUrl}/api/political-culture/chatbot/message`, {
        user_id: session?.userId,
        text: userMsg,
      });
    } catch (error) {
      logger.error("Failed to send chat message", {
        userId: session?.userId,
        error,
      });
      setMessages((m) => [
        ...m,
        {
          message: "Deu um problema, tenta novamente ou fala pro Felipe :)",
          role: "ai",
        },
      ]);
      setSending(false);
    }
  }

  return (
    <div
      className="chat-container"
      style={{
        width: isClient && isMobile ? "90vw" : "60vw",
        height: isClient && isMobile ? "85vh" : "95vh",
      }}
    >
      <div className="message-list">
        {loadingHistory ? (
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
          disabled={false}
          placeholder="Escreva sua mensagem…"
          rows={1}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              send();
            }
          }}
        />
        <button onClick={send} disabled={false}>
          Enviar
        </button>
      </div>
    </div>
  );
}
