"use client";
import { login } from "@/app/plants/actions/login";
import { useState, useEffect } from "react";
import ErrorMessage from "./ErrorMessage";
import { useRouter } from "next/navigation";
import "@/css/login.css";

export function LoginForm() {
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const router = useRouter();

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const formData = new FormData(event.currentTarget);
    const result = await login(formData);

    if (result?.message) {
      console.error(`An error occurred when trying to loggin the user`);

      setErrorMessage(result.message);
    }

    router.push("/chat");
  }

  useEffect(() => {
    if (errorMessage) {
      const timeout = setTimeout(() => {
        setErrorMessage(null);
      }, 3000);

      return () => clearTimeout(timeout);
    }
  }, [errorMessage]);

  return (
    <div className="login-container">
      <h1>Login</h1>

      <form onSubmit={handleSubmit}>
        <div>
          <input id="name" name="name" placeholder="Name" />
        </div>
        <div className="submitButton-container">
          <button type="submit">Authenticate</button>
        </div>
      </form>

      <ErrorMessage
        message={errorMessage}
        style={{
          fontSize: "20px",
          textAlign: "center",
          marginBottom: "15px",
          fontWeight: "bold",
        }}
      />
    </div>
  );
}
