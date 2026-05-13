"use client";
import { login } from "@/app/actions/login";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { logger } from "@/app/api/log/client-logger";
import Toast from "@/app/components/Toast";
import "@/plants/css/login.css";

export function LoginForm() {
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const router = useRouter();

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);

    const formData = new FormData(event.currentTarget);
    const result = await login(formData);

    if (result?.message) {
      logger.error("Login failed", { message: result.message });
      setErrorMessage(result.message);
      setSubmitting(false);
      return;
    }

    router.push("/plants/chat");
  }

  return (
    <div className="login-container">
      <h1>Login</h1>

      <form onSubmit={handleSubmit}>
        <div>
          <input id="name" name="name" placeholder="Name" />
        </div>
        <div className="submitButton-container">
          <button type="submit" disabled={submitting}>
            {submitting ? "Authenticating..." : "Authenticate"}
          </button>
        </div>
      </form>

      <Toast message={errorMessage} onClose={() => setErrorMessage(null)} />
    </div>
  );
}
