// Client HTTP de l'API : un seul endroit pour l'URL, l'authentification et les erreurs
import { API_URL } from "./env";

export type FieldError = { field: string; message: string };

export class ApiError extends Error {
  constructor(
    public status: number, // 0 = reseau / delai depasse
    message: string,
    public fieldErrors: FieldError[] = [],
    public network = false,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const TOKEN_KEY = "parc-token";
const TIMEOUT_MS = 15_000;

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token); else localStorage.removeItem(TOKEN_KEY);
  } catch { /* stockage indisponible */ }
}

/** Erreurs FastAPI : {detail: "...", field?} (regles metier) ou {detail: [{loc, msg}]} (validation). */
function parseError(status: number, data: unknown): ApiError {
  const detail = (data as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") {
    const field = (data as { field?: string | null }).field;
    return new ApiError(status, detail, field ? [{ field, message: detail }] : []);
  }
  if (Array.isArray(detail)) {
    const errors: FieldError[] = detail.map((d: { loc?: unknown[]; msg?: string }) => ({
      field: String(d.loc?.[d.loc.length - 1] ?? ""),
      message: d.msg ?? "Valeur invalide.",
    }));
    return new ApiError(status, errors[0]?.message ?? "Données invalides.", errors);
  }
  return new ApiError(status, `Erreur ${status}`);
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const token = getToken();
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch {
    throw new ApiError(0, "Impossible de joindre l’API.", [], true);
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown = null;
  try { data = text ? JSON.parse(text) : null; } catch { /* corps non JSON */ }
  if (!res.ok) throw parseError(res.status, data);
  return data as T;
}

export type Json = Record<string, unknown>;

export const api = {
  list: (endpoint: string) => request<Json[]>("GET", `/${endpoint}?limit=5000`),
  create: (endpoint: string, body: Json) => request<Json>("POST", `/${endpoint}`, body),
  update: (endpoint: string, id: string, body: Json) => request<Json>("PATCH", `/${endpoint}/${id}`, body),
  remove: (endpoint: string, id: string) => request<void>("DELETE", `/${endpoint}/${id}`),
  login: (nom_utilisateur: string, mot_de_passe: string) =>
    request<{ access_token: string }>("POST", "/auth/login", { nom_utilisateur, mot_de_passe }),
};
