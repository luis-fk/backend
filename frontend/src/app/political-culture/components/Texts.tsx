"use client";

import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { useSession } from "@/app/actions/useSession";
import { logger } from "@/app/api/log/client-logger";
import Toast from "@/app/components/Toast";
import {
  type UploadResult,
  useTextsSocket,
} from "@/political-culture/hooks/useTextsSocket";
import "@/political-culture/css/texts.css";

// The backend refuses bigger files; checking here saves sending them.
const MAX_PDF_BYTES = 100 * 1024 * 1024;

// The backend answers 401 once the session's token has expired (or the secrets
// changed); only a reload, which leads to the login page, fixes it.
const SESSION_EXPIRED = "Sua sessão expirou. Recarregue a página.";

interface LibraryText {
  id: number;
  title: string | null;
  author: string | null;
  description: string | null;
  word_count: number | null;
  added_by: string | null;
}

// The upload in progress: sending the file, then, once uploadId arrives, the
// backend reading it.
interface Upload {
  name: string;
  progress: number;
  uploadId: string | null;
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

function uploadError(error: unknown): string {
  if (!axios.isAxiosError(error)) return "Não foi possível enviar o PDF.";
  switch (error.response?.status) {
    case 401:
      return SESSION_EXPIRED;
    case 400:
      return "Envie um PDF de até 100 MB.";
    case 409:
      return "Este PDF já está na biblioteca.";
    default:
      return "Não foi possível enviar o PDF. Tente de novo.";
  }
}

function resultNotice(result: UploadResult, name: string): Notice {
  if (result.status === "ready") {
    return { message: `${name} entrou na biblioteca.`, severity: "success" };
  }
  return {
    message:
      result.reason === "no_text"
        ? `Não há texto para ler em ${name}. Um PDF escaneado precisa passar por OCR antes.`
        : `Não foi possível ler ${name}. Tente de novo.`,
    severity: "error",
  };
}

function details(text: LibraryText): string | null {
  const parts = [
    text.word_count === null
      ? null
      : `${text.word_count.toLocaleString("pt-BR")} palavras`,
    text.added_by === null ? null : `adicionado por ${text.added_by}`,
  ].filter((part) => part !== null);
  if (parts.length === 0) return null;
  const line = parts.join(", ");
  return line.charAt(0).toUpperCase() + line.slice(1);
}

export default function Texts(): React.ReactElement {
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

  useEffect(() => {
    if (!token || !serverUrl) return;

    const controller = new AbortController();
    axios
      .get<LibraryText[]>(`${serverUrl}/api/political-culture/texts`, {
        headers: { Authorization: `Bearer ${token}` },
        signal: controller.signal,
      })
      .then((res) => {
        setLibrary(res.data);
        setLoadFailed(false);
      })
      .catch((err: unknown) => {
        if (axios.isCancel(err)) return;
        logger.error("Failed to fetch the texts", { error: err });
        setLoadFailed(true);
        if (axios.isAxiosError(err) && err.response?.status === 401) {
          setNotice({ message: SESSION_EXPIRED, severity: "error" });
        }
      });

    return () => controller.abort();
  }, [token, serverUrl, reloads]);

  useTextsSocket({
    userId,
    token,
    serverUrl,
    onResult: (result) => {
      // Another tab's upload also fills the library.
      if (result.status === "ready") setReloads((count) => count + 1);
      if (!upload || result.upload_id !== upload.uploadId) return;
      setUpload(null);
      setNotice(resultNotice(result, upload.name));
    },
    onError: () => {
      if (!upload) return;
      setNotice({
        message:
          "A conexão caiu. Recarregue a página mais tarde para ver o texto na lista.",
        severity: "error",
      });
    },
  });

  function choose(event: React.ChangeEvent<HTMLInputElement>): void {
    const chosen = event.target.files?.[0] ?? null;
    if (chosen && (!isPdf(chosen) || chosen.size > MAX_PDF_BYTES)) {
      setNotice({
        message: "Escolha um PDF de até 100 MB.",
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
    if (!file || !token || !serverUrl || upload) return;

    const name = file.name;
    const form = new FormData();
    form.append("content", file);
    setUpload({ name, progress: 0, uploadId: null });

    try {
      const response = await axios.post<{ upload_id: string }>(
        `${serverUrl}/api/political-culture/texts`,
        form,
        {
          headers: { Authorization: `Bearer ${token}` },
          onUploadProgress: (progress) =>
            setUpload(
              (current) =>
                current && { ...current, progress: progress.progress ?? 0 },
            ),
        },
      );
      setUpload({ name, progress: 1, uploadId: response.data.upload_id });
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
    } catch (error) {
      logger.error("Failed to upload a text", { name, error });
      setUpload(null);
      setNotice({ message: uploadError(error), severity: "error" });
    }
  }

  return (
    <main className="page">
      <div className="page-header">
        <h1 className="page-title">Textos</h1>
        <p className="muted">
          A biblioteca que o assistente consulta. Qualquer pessoa do projeto
          pode adicionar um PDF.
        </p>
      </div>

      <form className="political-texts-upload" onSubmit={send}>
        <div className="field">
          <span id="text-file-label" className="field-label">
            PDF de até 100 MB
          </span>
          {/* The browser writes the native input's button and file name in its
              own language, so the input is hidden and this label, which opens
              it, shows them in Portuguese. */}
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
              Escolher PDF
            </span>
            <span
              id="text-file-name"
              className="political-texts-picker-name"
              data-empty={file === null}
            >
              {file?.name ?? "Nenhum arquivo escolhido"}
            </span>
          </label>
        </div>
        <button
          type="submit"
          className="button"
          disabled={!file || !token || Boolean(upload)}
        >
          Adicionar texto
        </button>
      </form>

      {upload && (
        <div className="political-texts-status" role="status">
          {upload.uploadId === null ? (
            <>
              <p>
                Enviando {upload.name}… {Math.round(upload.progress * 100)}%
              </p>
              <progress
                className="political-texts-progress"
                value={upload.progress}
                aria-label="Envio do PDF"
              />
            </>
          ) : (
            <>
              <p>Processando {upload.name}…</p>
              <progress
                className="political-texts-progress"
                aria-label="Leitura do PDF"
              />
              <p className="muted political-texts-hint">
                Um livro leva alguns minutos. Você pode sair desta página: o
                texto aparece na lista quando terminar.
              </p>
            </>
          )}
        </div>
      )}

      <section
        className="political-texts-library"
        aria-labelledby="library-title"
      >
        <h2 id="library-title" className="section-title">
          Biblioteca
        </h2>
        {session === null ? (
          <p className="muted">
            Não foi possível carregar a sua sessão. Recarregue a página.
          </p>
        ) : loadFailed && library === null ? (
          <p className="muted">Não foi possível carregar a biblioteca.</p>
        ) : library === null ? (
          <p className="muted">Carregando a biblioteca…</p>
        ) : library.length === 0 ? (
          <p className="muted">
            A biblioteca está vazia. Adicione o primeiro PDF.
          </p>
        ) : (
          <ul className="list">
            {library.map((text) => {
              const line = details(text);
              return (
                <li key={text.id} className="political-texts-item">
                  <h3 className="political-texts-title">
                    {text.title ?? "Sem título"}
                  </h3>
                  <p>{text.author ?? "Autor desconhecido"}</p>
                  {line && (
                    <p className="muted political-texts-details">{line}</p>
                  )}
                  {text.description && (
                    <details className="political-texts-summary">
                      <summary>Resumo</summary>
                      <p>{text.description}</p>
                    </details>
                  )}
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
