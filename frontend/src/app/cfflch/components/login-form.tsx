"use client";

import { useState } from "react";
import { login } from "@/cfflch/actions/login";
import { logger } from "@/app/api/log/client-logger";
import { useRouter } from "next/navigation";
import Toast from "@/app/components/Toast";
import "@/cfflch/css/login.css";

export default function LoginForm(): React.ReactElement {
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const router = useRouter();

  async function handleSubmit(
    event: React.FormEvent<HTMLFormElement>,
  ): Promise<void> {
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

    setSubmitting(false);
    router.push("/cfflch/search");
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