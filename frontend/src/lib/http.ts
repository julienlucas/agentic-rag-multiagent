/*
 * Requêtes vers le backend, sur le même domaine (Vercel relaie /api et /_allauth vers Railway ;
 * en dev, le proxy Vite). Session par cookie : `credentials: "include"` partout, et l'en-tête
 * X-CSRFToken (valeur du cookie `csrftoken`, posé par GET /api/me) sur tout ce qui modifie.
 */

// Toujours relatif : l'API est relayée sur le même domaine (rewrites de vercel.json, proxy Vite en
// dev). Un appel direct à Railway (ancien VITE_RAILWAY_API_URL) rendrait le cookie de session
// tiers, bloqué par Safari et bientôt par Chrome.
export const API_URL = "";

export class ApiError extends Error {
  status: number;
  data: unknown;
  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

export function getCookie(name: string): string | null {
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

export function csrfToken(): string {
  return getCookie("csrftoken") ?? "";
}

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/** fetch avec cookie de session et CSRF ; `body` objet = JSON, FormData = multipart. */
export async function request(
  path: string,
  { method = "GET", body, headers = {} }: { method?: string; body?: unknown; headers?: Record<string, string> } = {},
): Promise<Response> {
  const h: Record<string, string> = { ...headers };
  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    h["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  if (UNSAFE.has(method)) h["X-CSRFToken"] = csrfToken();
  return fetch(`${API_URL}${path}`, { method, body: payload, headers: h, credentials: "include" });
}

/** Corps JSON, ou ApiError avec le message `{error}` du backend. */
export async function parse<T>(response: Response): Promise<T> {
  let data: any = null;
  try {
    data = await response.json();
  } catch {
    /* corps vide */
  }
  if (!response.ok || data?.error) {
    throw new ApiError(data?.error || `Erreur serveur (${response.status})`, response.status, data);
  }
  return data as T;
}

export function json<T>(path: string, init?: Parameters<typeof request>[1]): Promise<T> {
  return request(path, init).then((r) => parse<T>(r));
}

export function errorMessage(err: unknown, fallback = "Erreur de connexion au serveur"): string {
  return err instanceof Error && err.message ? err.message : fallback;
}
