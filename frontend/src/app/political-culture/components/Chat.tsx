"use client";

import { useState, useEffect } from "react";
import {
  ChatContainer,
  MessageList,
  Message,
  MessageInput,
} from "@chatscope/chat-ui-kit-react";
import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";
import "@/political-culture/css/chat.css";
import axios from "axios";
import { useSession } from "@/app/actions/useSession";
import { useMediaQuery } from "@mui/material";

export interface MessageType {
  message: string;
  role: string;
}

export default function Chat() {
  const [messages, setMessages] = useState<MessageType[]>([
    {
      message: "Hello! How can I help you today?",
      role: "ai",
    },
  ]);
  const [activeSendButton, setActivateSendButton] = useState(false);
  const [messageInput, setMessageInput] = useState("");

  const session = useSession();
  const serverUrl = process.env.NEXT_PUBLIC_SERVER_URL;

  const isMobile = useMediaQuery("(max-width: 800px)");
  const chatWidth = isMobile ? "90vw" : "50vw";
  const chatHeight = isMobile ? "85vh" : "90vh";

  useEffect(() => {
    if (session?.userId) {
      async function fetchChatHistory() {
        const response = await axios.get(
          `${serverUrl}/api/chat-history/${session?.userId}`,
        );

        if (response.status === 200) {
          setMessages(response.data);
        } else if (response.status === 204) {
          setMessages([
            {
              message: "Hello! How can I help you today?",
              role: "ai",
            },
          ]);
        }
      }
      fetchChatHistory();
    }
  }, [session?.userId, serverUrl]);

  async function handleSendMessage() {
    if (messages[messages.length - 1]["role"] === "ai") {
      setActivateSendButton(true);

      const userMessage = messageInput;

      setMessages((prevMessages) => [
        ...prevMessages,
        { message: userMessage, role: "human" },
      ]);

      setMessageInput("");
      try {
        const response = await axios.post(`${serverUrl}/api/chatbot/message`, {
          user_id: session?.userId,
          message: userMessage,
        });

        setMessages((prevMessages) => [
          ...prevMessages,
          { message: response.data.response.message, role: "ai" },
        ]);
      } catch {
        console.error("Failed to send message to server");

        setMessages((prevMessages) => [
          ...prevMessages,
          {
            message: "Deu um problema, tenta novamente ou fala pro Felipe :)",
            role: "ai",
          },
        ]);
      } finally {
        setActivateSendButton(false);
      }
    } else {
      setMessageInput(messageInput);
    }
  }

  return (
    <ChatContainer
      suppressHydrationWarning
      style={{
        paddingTop: "30px",
        width: chatWidth,
        height: chatHeight,
        backgroundColor: "#292929",
      }}
    >
      <MessageList
        style={{
          padding: "10px",
          backgroundColor: "#292929",
        }}
      >
        {messages.map((msg, index) => (
          <Message
            style={{
              marginBottom: "10px",
              padding: "8px 12px",
              fontSize: "18px",
            }}
            key={index}
            type="html"
            model={{
              message: msg.message,
              sentTime: "just now",
              sender: msg.role,
              direction: msg.role === "human" ? "outgoing" : "incoming",
              position: "single",
            }}
          >
            {msg.message}
          </Message>
        ))}
      </MessageList>
      <MessageInput
        style={{
          padding: "5px 10px",
          borderRadius: "15px",
          border: "none",
          color: "white",
          backgroundColor: "#3e3e3e",
        }}
        value={messageInput}
        autoFocus={true}
        sendDisabled={activeSendButton}
        onChange={(value) => setMessageInput(value)}
        onSend={handleSendMessage}
        attachButton={false}
      />
    </ChatContainer>
  );
}
