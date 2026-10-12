/*
 * Client django-allauth « headless », client navigateur (session par cookie).
 * Réponses allauth : `{status, data, meta}` ; erreurs de formulaire : `{status: 400, errors: [{message, param}]}`.
 * Un 401 n'est pas forcément un échec : il porte les étapes encore à franchir (`data.flows[].is_pending`),
 * par exemple la vérification de l'e-mail après une inscription.
 */
import { API_URL, csrfToken, request } from "@/lib/http";

const BASE = "/_allauth/browser/v1";

type Flow = { id: string; is_pending?: boolean };
type AllauthBody = {
  status: number;
  data?: { flows?: Flow[]; user?: { email?: string } };
  errors?: { message: string; param?: string; code?: string }[];
  meta?: { is_authenticated?: boolean };
};

export type AuthResult =
  | { kind: "authenticated" }
  | { kind: "verify_email" }
  | { kind: "password_reset_code" }
  | { kind: "error"; message: string; field?: string };

async function call(path: string, method: string, body?: unknown): Promise<{ status: number; body: AllauthBody }> {
  // Le cookie csrftoken doit exister avant le premier POST : GET /api/me le pose toujours.
  if (method !== "GET" && !csrfToken()) await request("/api/me").catch(() => undefined);
  const r = await request(`${BASE}${path}`, { method, body });
  let parsed: AllauthBody = { status: r.status };
  try {
    parsed = await r.json();
  } catch {
    /* corps vide */
  }
  return { status: r.status, body: parsed };
}

function pending(body: AllauthBody, id: string) {
  return Boolean(body.data?.flows?.some((f) => f.id === id && f.is_pending));
}

function toResult({ status, body }: { status: number; body: AllauthBody }): AuthResult {
  if (status === 200) return { kind: "authenticated" };
  if (status === 401 && pending(body, "verify_email")) return { kind: "verify_email" };
  if (status === 401 && pending(body, "password_reset_by_code")) return { kind: "password_reset_code" };
  const first = body.errors?.[0];
  if (first) return { kind: "error", message: first.message, field: first.param };
  if (status === 409) return { kind: "error", message: "Vous êtes déjà connecté." };
  if (status === 429) return { kind: "error", message: "Trop de tentatives, réessayez dans quelques minutes." };
  return { kind: "error", message: `Erreur inattendue (${status}).` };
}

export const auth = {
  async signup(email: string, password: string) {
    return toResult(await call("/auth/signup", "POST", { email, password }));
  },
  async login(email: string, password: string) {
    return toResult(await call("/auth/login", "POST", { email, password }));
  },
  async verifyEmail(code: string) {
    return toResult(await call("/auth/email/verify", "POST", { key: code.trim() }));
  },
  async resendVerification() {
    const r = await call("/auth/email/verify/resend", "POST");
    return r.status === 200 || r.status === 401 ? null : toResult(r);
  },
  async logout() {
    await call("/auth/session", "DELETE");
  },
  async requestPasswordReset(email: string) {
    return toResult(await call("/auth/password/request", "POST", { email }));
  },
  async resetPassword(code: string, password: string) {
    return toResult(await call("/auth/password/reset", "POST", { key: code.trim(), password }));
  },
  async changePassword(currentPassword: string, newPassword: string) {
    return toResult(
      await call("/account/password/change", "POST", {
        current_password: currentPassword,
        new_password: newPassword,
      }),
    );
  },
  /** Connexion Google : formulaire POST classique, le navigateur suit les redirections. */
  async google(callbackUrl = "/app") {
    if (!csrfToken()) await request("/api/me").catch(() => undefined);
    const form = document.createElement("form");
    form.method = "POST";
    form.action = `${API_URL}${BASE}/auth/provider/redirect`;
    const fields = {
      provider: "google",
      callback_url: callbackUrl,
      process: "login",
      csrfmiddlewaretoken: csrfToken(),
    };
    for (const [name, value] of Object.entries(fields)) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = name;
      input.value = value;
      form.appendChild(input);
    }
    document.body.appendChild(form);
    form.submit();
  },
};
