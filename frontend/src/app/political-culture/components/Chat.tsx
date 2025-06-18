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
      message: "Hello! How can I help you today?",
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

  async function send() {
    if (sending || !input.trim()) return;
    setSending(true);
    const userMsg = input.trim();
    setMessages((m) => [...m, { message: userMsg, role: "human" }]);
    setInput("");

    try {
      const res = await axios.post(
        `${serverUrl}/api/political-culture/chatbot/message`,
        {
          user_id: session?.userId,
          text: userMsg,
        },
      );
      setMessages((m) => [...m, { message: res.data.response, role: "ai" }]);
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
          disabled={sending}
          placeholder="Type your message…"
          rows={1}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <button onClick={send} disabled={sending || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}
