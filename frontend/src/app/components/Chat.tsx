"use client"; // Ensures this is a client-side component

import { useState } from "react";
import {
  ChatContainer,
  MessageList,
  Message,
  MessageInput,
} from "@chatscope/chat-ui-kit-react";
import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";
import "@/css/chat.css";
import axios from "axios";

interface MessageType {
  message: string;
  sender: string;
}

export default function Chat() {
  const [messages, setMessages] = useState<MessageType[]>([
    {
      message: "Hello! How can I help you today?",
      sender: "ai",
    },
  ]);
  const [activeSendButton, setSendButton] = useState(true);
  const [messageInput, setMessageInput] = useState("");

  async function handleSendMessage() {
    console.log(messages);
    if (messages[messages.length - 1]["sender"] === "ai") {
      setSendButton(true);

      const userMessage = messageInput;

      setMessages((prevMessages) => [
        ...prevMessages,
        { message: userMessage, sender: "user" },
      ]);

      setMessageInput("");
      try {
        const response = await axios.post("http://localhost:8000/message/", {
          user_id: 2,
          message: userMessage,
        });

        setMessages((prevMessages) => [
          ...prevMessages,
          { message: response.data.response, sender: "ai" },
        ]);
      } catch {
        console.error("Error sending message:");
      } finally {
        setSendButton(false);
      }
    } else {
      setMessageInput(messageInput);
    }
  }

  return (
    <ChatContainer
      style={{
        paddingTop: "30px",
        width: "50vw",
        height: "90vh",
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
              sender: msg.sender,
              direction: msg.sender === "user" ? "outgoing" : "incoming",
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
