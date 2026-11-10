"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/plants/actions/login";
import { logger } from "@/app/api/log/client-logger";
import { localePath } from "@/app/i18n";
import { useLocale } from "@/app/useLocale";

export function LoginForm(): React.ReactElement {
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const router = useRouter();
  const lang = useLocale();

  async function handleSubmit(
    event: React.FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();
    setSubmitting(true);
    setErrorMessage(null);

    const formData = new FormData(event.currentTarget);
    const result = await login(formData);

    if (result?.message) {
      logger.error("Login failed", { message: result.message });
      setErrorMessage(result.message);
      setSubmitting(false);
      return;
    }

    setSubmitting(false);
    router.push(localePath(lang, "/plants/chat"));
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="name" className="field-label">
          Seu nome
        </label>
        <input
          id="name"
          name="name"
          type="text"
          className="input"
          placeholder="Maria Souza"
          aria-invalid={errorMessage ? true : undefined}
          aria-describedby={errorMessage ? "name-error" : undefined}
        />
        {errorMessage && (
          <p id="name-error" className="form-error" role="alert">
            {errorMessage}
          </p>
        )}
      </div>
      <button type="submit" className="button" disabled={submitting}>
        {submitting ? "Entrando…" : "Entrar"}
      </button>
    </form>
  );
}
