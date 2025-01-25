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

export default function Chat() {
  const [messages, setMessages] = useState([{ message: "", sender: "" }]);
  const [messageInput, setMessageInput] = useState("");

  const handleSendMessage = () => {
    if (messageInput.trim() !== "") {
      setMessages([...messages, { message: messageInput, sender: "user" }]);
      setMessageInput("");
    }
  };

  return (
    <ChatContainer
      style={{
        paddingTop: "30px",
        width: "40vw",
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
            }}
            key={index}
            model={{
              message: msg.message,
              sentTime: "just now",
              sender: msg.sender,
              direction: msg.sender === "user" ? "outgoing" : "incoming",
              position: "single",
            }}
          />
        ))}
      </MessageList>
      <MessageInput
        placeholder="Type a message..."
        style={{
          padding: "5px 10px",
          borderRadius: "15px",
          border: "none",
          color: "white",
          backgroundColor: "#3e3e3e",
        }}
        value={messageInput}
        onChange={(e) => setMessageInput(e)}
        onSend={handleSendMessage}
        attachButton={false}
      />
    </ChatContainer>
  );
}
