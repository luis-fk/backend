import axios from "axios";

// The backend answers 401 once the session's token has expired (or the secrets
// changed); only a reload, which leads to the login page, fixes it.
const SESSION_EXPIRED = "Sua sessão expirou. Recarregue a página.";

// The message for a failed call to the backend.
export function errorMessage(error: unknown, fallback: string): string {
  return axios.isAxiosError(error) && error.response?.status === 401
    ? SESSION_EXPIRED
    : fallback;
}
