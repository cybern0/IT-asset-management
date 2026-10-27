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

/** Utilisateur connecte, tel que renvoye par /auth/login et /auth/me. */
export type AuthUser = {
  id: number;
  nom_utilisateur: string;
  role_id: number;
  role_code: string | null; // ADMIN, GESTIONNAIRE, LECTURE...
};

const TOKEN_KEY = "parc-token";
const TIMEOUT_MS = 15_000;

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}

// Appele quand l'API repond 401 (jeton expire ou refuse) : l'interface revient a l'ecran de connexion.
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null): void {
  onUnauthorized = fn;
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

type Init = { json?: unknown; form?: FormData; timeout?: number };

/** Appel HTTP commun : jeton, delai, erreurs reseau. Leve ApiError si la reponse n'est pas 2xx. */
async function send(method: string, path: string, init: Init = {}): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), init.timeout ?? TIMEOUT_MS);
  const token = getToken();
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers: {
        ...(init.json !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: init.form ?? (init.json !== undefined ? JSON.stringify(init.json) : undefined),
      signal: controller.signal,
    });
  } catch {
    throw new ApiError(0, "Impossible de joindre l’API.", [], true);
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) {
    if (res.status === 401 && path !== "/auth/login") {
      setToken(null);
      onUnauthorized?.();
    }
    let data: unknown = null;
    try { data = await res.json(); } catch { /* corps non JSON */ }
    throw parseError(res.status, data);
  }
  return res;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await send(method, path, { json: body });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : null) as T;
}

const UPLOAD_TIMEOUT_MS = 60_000;

export type Json = Record<string, unknown>;

export const api = {
  list: (endpoint: string) => request<Json[]>("GET", `/${endpoint}?limit=5000`),
  create: (endpoint: string, body: Json) => request<Json>("POST", `/${endpoint}`, body),
  update: (endpoint: string, id: string, body: Json) => request<Json>("PATCH", `/${endpoint}/${id}`, body),
  remove: (endpoint: string, id: string) => request<void>("DELETE", `/${endpoint}/${id}`),
  get: <T = Json>(path: string) => request<T>("GET", path),
  post: <T = Json>(path: string) => request<T>("POST", path),
  del: (path: string) => request<void>("DELETE", path),
  /** Envoi de fichier (multipart) : le navigateur fixe lui-meme le Content-Type. */
  upload: async <T = Json>(path: string, form: FormData): Promise<T> =>
    (await send("POST", path, { form, timeout: UPLOAD_TIMEOUT_MS })).json() as Promise<T>,
  /** Fichier binaire (image, PDF) : l'authentification passe par l'en-tete, pas par une URL. */
  blob: async (path: string): Promise<Blob> => (await send("GET", path, { timeout: UPLOAD_TIMEOUT_MS })).blob(),
  login: (nom_utilisateur: string, mot_de_passe: string) =>
    request<{ access_token: string; user: AuthUser }>("POST", "/auth/login", { nom_utilisateur, mot_de_passe }),
};
