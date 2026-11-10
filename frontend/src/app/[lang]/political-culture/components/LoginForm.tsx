"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/political-culture/actions/login";
import { logger } from "@/app/api/log/client-logger";
import { localePath } from "@/app/i18n";
import { useLocale } from "@/app/useLocale";
import { politicalCultureDictionary } from "@/political-culture/dictionary";

export function LoginForm(): React.ReactElement {
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const router = useRouter();
  const lang = useLocale();
  const t = politicalCultureDictionary[lang].login;

  async function handleSubmit(
    event: React.FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();
    setSubmitting(true);
    setErrorMessage(null);

    const formData = new FormData(event.currentTarget);
    const result = await login(lang, formData);

    if (result?.message) {
      logger.error("Login failed", { message: result.message });
      setErrorMessage(result.message);
      setSubmitting(false);
      return;
    }

    setSubmitting(false);
    router.push(localePath(lang, "/political-culture/chat"));
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="name" className="field-label">
          {t.nameLabel}
        </label>
        <input
          id="name"
          name="name"
          type="text"
          className="input"
          placeholder={t.namePlaceholder}
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
        {submitting ? t.submitting : t.submit}
      </button>
    </form>
  );
}
