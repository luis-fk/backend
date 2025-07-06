"use client";

import { useEffect, useState, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import axios from "axios";
import { useSession } from "@/app/actions/useSession";
import { useMediaQuery } from "@mui/material";
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
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const session = useSession();
  const serverUrl = process.env.NEXT_PUBLIC_SERVER_URL;

  const isMobile = useMediaQuery("(max-width: 800px)");

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
    if (!session?.userId) return;
    axios
      .get(`${serverUrl}/api/political-culture/chat-history/${session.userId}`)
      .then((res) => {
        if (res.status === 200) setMessages(res.data);
      })
      .catch(() => {});
  }, [session?.userId]);

  // useEffect(() => {
  //   if (!session?.userId) return;

  //   const eventSource = new EventSource(
  //     `${serverUrl}/api/political-culture/chat-stream/${session.userId}/`,
  //   );

  //   eventSource.onmessage = (event) => {
  //     const { message, role } = JSON.parse(event.data);
  //     setMessages((previous) => [...previous, { message, role }]);
  //   };

  //   eventSource.onerror = () => {
  //     console.error("SSE error, closing connection");
  //     eventSource.close();
  //   };

  //   return () => {
  //     eventSource.close();
  //   };
  // }, [session?.userId, serverUrl]);

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
    } catch {
      setMessages((m) => [
        ...m,
        {
          message: "Deu um problema, tenta novamente ou fala pro Felipe :)",
          role: "ai",
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div
      className="chat-container"
      style={{
        width: isMobile ? "90vw" : "60vw",
        height: isMobile ? "85vh" : "95vh",
      }}
    >
      <div className="message-list">
        {messages.map((msg, i) => (
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
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="input-area">
        <textarea
          ref={textareaRef}
          className="chat-input"
          value={input}
          disabled={true}
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
        <button onClick={send} disabled={true}>
          Enviar
        </button>
      </div>
    </div>
  );
}
