"use client";

import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { useSession } from "@/app/actions/useSession";
import { logger } from "@/app/api/log/client-logger";
import Toast from "@/app/components/Toast";
import { commonDictionary } from "@/app/dictionary";
import type { Locale } from "@/app/i18n";
import { useLocale } from "@/app/useLocale";
import { politicalCultureDictionary } from "@/political-culture/dictionary";
import {
  type UploadResult,
  useTextsSocket,
} from "@/political-culture/hooks/useTextsSocket";
import "@/political-culture/css/texts.css";

// The backend refuses bigger files; checking here saves sending them.
const MAX_PDF_BYTES = 100 * 1024 * 1024;

interface LibraryText {
  id: number;
  title: string | null;
  author: string | null;
  description: string | null;
  word_count: number | null;
  added_by: string | null;
  // Whether the assistant uses the text in this user's analyses.
  selected: boolean;
}

// The upload in progress: sending the file, then, once sent, the backend reading
// it. The page picks the id, so a result that comes before the 202 still matches.
interface Upload {
  id: string;
  name: string;
  progress: number;
  sent: boolean;
}

interface Notice {
  message: string;
  severity: "error" | "success";
}

function isPdf(file: File): boolean {
  return (
    file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")
  );
}

function uploadError(error: unknown, lang: Locale): string {
  const t = politicalCultureDictionary[lang].texts.upload;
  if (!axios.isAxiosError(error)) return t.failed;
  switch (error.response?.status) {
    // The backend answers 401 once the session's token has expired (or the
    // secrets changed); only a reload, which leads to the login page, fixes it.
    case 401:
      return commonDictionary[lang].session.expired;
    case 400:
      return t.tooBig;
    case 409:
      return t.duplicate;
    default:
      return t.retry;
  }
}

function resultNotice(
  result: UploadResult,
  name: string,
  lang: Locale,
): Notice {
  const t = politicalCultureDictionary[lang].texts.upload;
  if (result.status === "ready") {
    return { message: t.ready(name), severity: "success" };
  }
  return {
    message: result.reason === "no_text" ? t.noText(name) : t.readFailed(name),
    severity: "error",
  };
}

function details(text: LibraryText, lang: Locale): string | null {
  const t = politicalCultureDictionary[lang].texts.library;
  const parts = [
    text.word_count === null
      ? null
      : t.words(text.word_count.toLocaleString(lang)),
    text.added_by === null ? null : t.addedBy(text.added_by),
  ].filter((part) => part !== null);
  if (parts.length === 0) return null;
  const line = parts.join(", ");
  return line.charAt(0).toUpperCase() + line.slice(1);
}

function selectedSummary(library: LibraryText[], lang: Locale): string {
  const selected = library.filter((text) => text.selected).length;
  return politicalCultureDictionary[lang].texts.library.summary(
    selected,
    library.length,
  );
}

export default function Texts(): React.ReactElement {
  const lang = useLocale();
  const t = politicalCultureDictionary[lang].texts;
  const common = commonDictionary[lang];
  const session = useSession("political-culture");
  const userId = session?.userId;
  const token = session?.token;
  const serverUrl = process.env.NEXT_PUBLIC_SERVER_URL;

  // null until the first load; a reload keeps the list on screen.
  const [library, setLibrary] = useState<LibraryText[] | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [reloads, setReloads] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [upload, setUpload] = useState<Upload | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  // A list read while a tick was being saved may come back with the old tick,
  // so it is read again: these count the saves in flight and the saves done.
  const ticksSaving = useRef(0);
  const ticksSaved = useRef(0);
  const reloadAfterTicks = useRef(false);

  useEffect(() => {
    if (!token || !serverUrl) return;

    const controller = new AbortController();
    const savedBefore = ticksSaved.current;
    axios
      .get<LibraryText[]>(`${serverUrl}/api/political-culture/texts`, {
        headers: { Authorization: `Bearer ${token}` },
        signal: controller.signal,
      })
      .then((res) => {
        if (ticksSaving.current > 0) {
          reloadAfterTicks.current = true;
          return;
        }
        if (ticksSaved.current !== savedBefore) {
          setReloads((count) => count + 1);
          return;
        }
        setLibrary(res.data);
        setLoadFailed(false);
      })
      .catch((err: unknown) => {
        if (axios.isCancel(err)) return;
        logger.error("Failed to fetch the texts", { error: err });
        setLoadFailed(true);
        if (axios.isAxiosError(err) && err.response?.status === 401) {
          setNotice({ message: common.session.expired, severity: "error" });
        }
      });

    return () => controller.abort();
  }, [token, serverUrl, reloads, common]);

  const socket = useTextsSocket({
    userId,
    token,
    serverUrl,
    onResult: (result) => {
      // Another tab's upload also fills the library.
      if (result.status === "ready") setReloads((count) => count + 1);
      if (!upload || result.upload_id !== upload.id) return;
      setUpload(null);
      setNotice(resultNotice(result, upload.name, lang));
    },
    onClose: () => {
      if (!upload) return;
      setUpload(null);
      setNotice({
        message: t.upload.dropped(upload.name, upload.sent),
        severity: "error",
      });
    },
  });

  function choose(event: React.ChangeEvent<HTMLInputElement>): void {
    const chosen = event.target.files?.[0] ?? null;
    if (chosen && (!isPdf(chosen) || chosen.size > MAX_PDF_BYTES)) {
      setNotice({
        message: t.upload.invalidFile,
        severity: "error",
      });
      event.target.value = "";
      setFile(null);
      return;
    }
    setFile(chosen);
  }

  async function send(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!file || !token || !serverUrl || upload || socket !== "open") return;

    const id = crypto.randomUUID();
    const name = file.name;
    const form = new FormData();
    form.append("content", file);
    form.append("upload_id", id);
    setUpload({ id, name, progress: 0, sent: false });
    // The updates below check the id: the result, or a dropped socket, may have
    // ended this upload already.
    const update = (change: Partial<Upload>): void =>
      setUpload((current) =>
        current?.id === id ? { ...current, ...change } : current,
      );

    try {
      await axios.post(`${serverUrl}/api/political-culture/texts`, form, {
        headers: { Authorization: `Bearer ${token}` },
        onUploadProgress: (progress) =>
          update({ progress: progress.progress ?? 0 }),
      });
      update({ progress: 1, sent: true });
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
    } catch (error) {
      logger.error("Failed to upload a text", { name, error });
      setUpload((current) => (current?.id === id ? null : current));
      setNotice({ message: uploadError(error, lang), severity: "error" });
    }
  }

  function markSelected(id: number, selected: boolean): void {
    setLibrary(
      (current) =>
        current &&
        current.map((text) => (text.id === id ? { ...text, selected } : text)),
    );
  }

  // Shows the tick at once and takes it back if the backend refuses it.
  async function toggle(text: LibraryText): Promise<void> {
    if (!token || !serverUrl) return;
    const selected = !text.selected;
    markSelected(text.id, selected);
    ticksSaving.current += 1;
    // Saves that overlap can reach the server in any order.
    if (ticksSaving.current > 1) reloadAfterTicks.current = true;

    try {
      await axios.put(
        `${serverUrl}/api/political-culture/texts/${text.id}/selection`,
        { selected },
        { headers: { Authorization: `Bearer ${token}` } },
      );
    } catch (error) {
      logger.error("Failed to save a text's tick", { id: text.id, error });
      markSelected(text.id, !selected);
      // The revert assumes the server kept the old tick, which a lost answer
      // or another save in flight can make wrong.
      reloadAfterTicks.current = true;
      setNotice({
        message:
          axios.isAxiosError(error) && error.response?.status === 401
            ? common.session.expired
            : t.library.saveFailed,
        severity: "error",
      });
    } finally {
      ticksSaving.current -= 1;
      ticksSaved.current += 1;
      if (ticksSaving.current === 0 && reloadAfterTicks.current) {
        reloadAfterTicks.current = false;
        setReloads((count) => count + 1);
      }
    }
  }

  return (
    <main className="page">
      <div className="page-header">
        <h1 className="page-title">{t.title}</h1>
        <p className="muted">{t.intro}</p>
      </div>

      <form className="political-texts-upload" onSubmit={send}>
        <div className="field">
          <span id="text-file-label" className="field-label">
            {t.upload.label}
          </span>
          {/* The browser writes the native input's button and file name in its
              own language, so the input is hidden and this label, which opens
              it, shows them in the page's language. */}
          <label className="political-texts-picker">
            <input
              ref={fileInput}
              id="text-file"
              type="file"
              accept="application/pdf,.pdf"
              className="visually-hidden"
              aria-labelledby="text-file-label"
              aria-describedby="text-file-name"
              disabled={Boolean(upload)}
              onChange={choose}
            />
            <span className="political-texts-picker-button" aria-hidden="true">
              {t.upload.choose}
            </span>
            <span
              id="text-file-name"
              className="political-texts-picker-name"
              data-empty={file === null}
            >
              {file?.name ?? t.upload.noFile}
            </span>
          </label>
        </div>
        <button
          type="submit"
          className="button"
          disabled={!file || !token || Boolean(upload) || socket !== "open"}
        >
          {t.upload.submit}
        </button>
      </form>

      {socket === "closed" && (
        <p className="form-error">{t.upload.socketClosed}</p>
      )}

      {upload && (
        <div className="political-texts-status" role="status">
          {!upload.sent ? (
            <>
              <p>
                {t.upload.sending(
                  upload.name,
                  Math.round(upload.progress * 100),
                )}
              </p>
              <progress
                className="political-texts-progress"
                value={upload.progress}
                aria-label={t.upload.sendingLabel}
              />
            </>
          ) : (
            <>
              <p>{t.upload.processing(upload.name)}</p>
              <progress
                className="political-texts-progress"
                aria-label={t.upload.processingLabel}
              />
              <p className="muted political-texts-hint">
                {t.upload.processingHint}
              </p>
            </>
          )}
        </div>
      )}

      <section
        className="political-texts-library"
        aria-labelledby="library-title"
      >
        <div className="political-texts-library-header">
          <h2 id="library-title" className="section-title">
            {t.library.title}
          </h2>
          {library && library.length > 0 && (
            <p className="muted">{selectedSummary(library, lang)}</p>
          )}
        </div>
        {session === null ? (
          <p className="muted">{common.session.loadFailed}</p>
        ) : loadFailed && library === null ? (
          <p className="muted">{t.library.loadFailed}</p>
        ) : library === null ? (
          <p className="muted">{t.library.loading}</p>
        ) : library.length === 0 ? (
          <p className="muted">{t.library.empty}</p>
        ) : (
          <ul className="list">
            {library.map((text) => {
              const line = details(text, lang);
              return (
                <li key={text.id} className="political-texts-item">
                  <div className="political-texts-main">
                    <h3 className="political-texts-title">
                      {text.title ?? t.library.untitled}
                    </h3>
                    <p>{text.author ?? t.library.unknownAuthor}</p>
                    {line && (
                      <p className="muted political-texts-details">{line}</p>
                    )}
                    {text.description && (
                      <details className="political-texts-summary">
                        <summary>{t.library.descriptionLabel}</summary>
                        <p>{text.description}</p>
                      </details>
                    )}
                  </div>
                  <label className="checkbox political-texts-pick">
                    <input
                      type="checkbox"
                      checked={text.selected}
                      onChange={() => toggle(text)}
                    />
                    {t.library.pick}
                    <span className="visually-hidden">
                      : {text.title ?? t.library.untitledText}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <Toast
        message={notice?.message ?? null}
        severity={notice?.severity}
        onClose={() => setNotice(null)}
      />
    </main>
  );
}
