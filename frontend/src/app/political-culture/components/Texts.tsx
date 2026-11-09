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

function uploadError(error: unknown): string {
  if (!axios.isAxiosError(error)) return "Não foi possível enviar o PDF.";
  switch (error.response?.status) {
    case 401:
      return SESSION_EXPIRED;
    case 400:
      return "Envie um PDF de até 100 MB.";
    case 409:
      return "Este PDF já está na biblioteca, ou ainda está sendo lido.";
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

function selectedSummary(library: LibraryText[]): string {
  const selected = library.filter((text) => text.selected).length;
  const texts = library.length === 1 ? "texto" : "textos";
  return `${selected} de ${library.length} ${texts} nas suas análises`;
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

  const socket = useTextsSocket({
    userId,
    token,
    serverUrl,
    onResult: (result) => {
      // Another tab's upload also fills the library.
      if (result.status === "ready") setReloads((count) => count + 1);
      if (!upload || result.upload_id !== upload.id) return;
      setUpload(null);
      setNotice(resultNotice(result, upload.name));
    },
    onClose: () => {
      if (!upload) return;
      setUpload(null);
      setNotice({
        message: `A conexão caiu durante ${upload.sent ? "a leitura" : "o envio"} de ${upload.name}. Recarregue a página: se a leitura terminar, o texto aparece na lista.`,
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
      setNotice({ message: uploadError(error), severity: "error" });
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

    try {
      await axios.put(
        `${serverUrl}/api/political-culture/texts/${text.id}/selection`,
        { selected },
        { headers: { Authorization: `Bearer ${token}` } },
      );
    } catch (error) {
      logger.error("Failed to save a text's tick", { id: text.id, error });
      markSelected(text.id, !selected);
      setNotice({
        message:
          axios.isAxiosError(error) && error.response?.status === 401
            ? SESSION_EXPIRED
            : "Não foi possível salvar a sua escolha. Tente de novo.",
        severity: "error",
      });
    }
  }

  return (
    <main className="page">
      <div className="page-header">
        <h1 className="page-title">Textos</h1>
        <p className="muted">
          A biblioteca do assistente. Marque os textos que ele usa nas suas
          análises: cada pessoa escolhe os seus, e um texto novo começa
          desmarcado.
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
          disabled={!file || !token || Boolean(upload) || socket !== "open"}
        >
          Adicionar texto
        </button>
      </form>

      {socket === "closed" && (
        <p className="form-error">
          A conexão com o servidor caiu. Recarregue a página para adicionar
          textos.
        </p>
      )}

      {upload && (
        <div className="political-texts-status" role="status">
          {!upload.sent ? (
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
        <div className="political-texts-library-header">
          <h2 id="library-title" className="section-title">
            Biblioteca
          </h2>
          {library && library.length > 0 && (
            <p className="muted">{selectedSummary(library)}</p>
          )}
        </div>
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
                  <div className="political-texts-main">
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
                  </div>
                  <label className="checkbox political-texts-pick">
                    <input
                      type="checkbox"
                      checked={text.selected}
                      onChange={() => toggle(text)}
                    />
                    Usar nas minhas análises
                    <span className="visually-hidden">
                      : {text.title ?? "texto sem título"}
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
