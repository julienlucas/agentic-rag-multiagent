import { API_URL, ApiError, json, parse, request } from "@/lib/http";

export { ApiError };

/* ---------- Types partagés ---------- */

export type Citation = {
  n: number;
  source: string;
  page: number | null;
  locator: string;
  excerpt: string;
  /** De quoi rouvrir le document au passage cité (absents des réponses antérieures). */
  file_hash?: string | null;
  /**
   * Original du document : /static/… pour un exemple, /api/documents/…/file pour un dépôt de la
   * démo (le frontend y ajoute session_id), /api/app/documents/<id>/file dans l'espace connecté.
   */
  pdf_url?: string | null;
  /** Passage entier transmis au modèle, pour le surligner dans la page. */
  text?: string;
  /** Espace connecté : le document cité (repli texte quand pdf_url est null). */
  document_id?: string | null;
};

/** URL de l'original : l'API sert les fichiers déposés (contrôle par espace), le frontend les exemples. */
export function documentUrl(pdfUrl: string, sessionId?: string): string {
  if (pdfUrl.startsWith("/api/app/")) return `${API_URL}${pdfUrl}`;
  if (pdfUrl.startsWith("/api/")) return `${API_URL}${pdfUrl}?session_id=${encodeURIComponent(sessionId ?? "")}`;
  return pdfUrl;
}

/* ---------- Tarifs (public) ---------- */

export type Pack = { id: string; price_eur: number; credits: number };
export type Pricing = {
  credit_value_eur: number;
  question_credits: number;
  page_credits: number;
  free: { documents: number; pages: number; welcome_credits: number };
  paid: { documents: number; pages: number };
  packs: Pack[];
  formats: string[];
};

/** Repli identique au contrat (docs/api-produit.md) si GET /api/pricing échoue. */
export const FALLBACK_PRICING: Pricing = {
  credit_value_eur: 0.01,
  question_credits: 20,
  page_credits: 1,
  free: { documents: 20, pages: 1000, welcome_credits: 300 },
  paid: { documents: 500, pages: 20000 },
  packs: [
    { id: "pack_10", price_eur: 10, credits: 1000 },
    { id: "pack_25", price_eur: 25, credits: 2600 },
    { id: "pack_50", price_eur: 50, credits: 5400 },
    { id: "pack_100", price_eur: 100, credits: 11000 },
  ],
  formats: [
    ".pdf", ".docx", ".pptx", ".odt", ".rtf", ".png", ".jpg", ".jpeg", ".webp", ".tiff",
    ".txt", ".md", ".html", ".xlsx", ".csv",
  ],
};

/* ---------- Session ---------- */

export type Me = {
  user: { email: string };
  workspace: {
    id: string;
    plan: "free" | "paid";
    balance: number;
    documents_count: number;
    pages_count: number;
    max_documents: number;
    max_pages: number;
  };
};

/* ---------- Espace connecté ---------- */

export type DocumentStatus = "queued" | "processing" | "ready" | "error";
export type AppDocument = {
  id: string;
  name: string;
  kind: string;
  size: number;
  pages: number;
  status: DocumentStatus;
  error: string | null;
  credits: number;
  created_at: string;
  file_url: string | null;
};

export type Message = {
  id: string;
  question: string;
  answer: string;
  verification_report: string;
  citations: Citation[];
  credits: number;
  created_at: string;
  feedback_token: string | null;
};

export type ConversationSummary = { id: string; title: string; updated_at: string };
export type Conversation = { id: string; title: string; messages: Message[] };

export type CreditEntry = {
  id: string;
  delta: number;
  reason: "welcome" | "purchase" | "question" | "indexing" | "refund";
  label: string;
  created_at: string;
};

export const appApi = {
  pricing: () => json<Pricing>("/api/pricing"),
  me: () => json<Me>("/api/me"),

  documents: () => json<{ documents: AppDocument[] }>("/api/app/documents"),
  upload(files: File[]) {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return json<{ documents: AppDocument[]; balance: number }>("/api/app/documents", { method: "POST", body: form });
  },
  deleteDocument: (id: string) => json<{ ok: true }>(`/api/app/documents/${id}`, { method: "DELETE" }),
  pageText: (documentId: string, page: number) =>
    json<{ page: number; text: string }>(
      `/api/app/documents/page?${new URLSearchParams({ document: documentId, page: String(page) })}`,
    ),

  ask: (question: string, conversationId?: string | null) =>
    json<{ conversation_id: string; message: Message; balance: number }>("/api/app/ask", {
      method: "POST",
      body: conversationId ? { question, conversation_id: conversationId } : { question },
    }),
  conversations: () => json<{ conversations: ConversationSummary[] }>("/api/app/conversations"),
  conversation: (id: string) => json<Conversation>(`/api/app/conversations/${id}`),
  deleteConversation: (id: string) => json<{ ok: true }>(`/api/app/conversations/${id}`, { method: "DELETE" }),
  feedback: (token: string, score: 0 | 1, comment?: string) =>
    json<{ message: string }>("/api/app/feedback", { method: "POST", body: { feedback_token: token, score, comment } }),

  credits: () => json<{ balance: number; entries: CreditEntry[]; billing_enabled: boolean }>("/api/app/credits"),
  checkout: (pack: string) => json<{ url: string }>("/api/app/checkout", { method: "POST", body: { pack } }),

  deleteAccount: () => json<{ ok: true }>("/api/app/account", { method: "DELETE" }),
};

/* ---------- Démo publique (session_id, sans compte) ---------- */

export type LoadFileResponse = { message: string; chunks_count: number; filename: string };
export type PageTextResponse = { file_hash: string; page: number; text: string };
export type ProcessQuestionResponse = {
  draft_answer: string;
  verification_report: string;
  citations: Citation[];
  /** Jeton signé pour voter sur la réponse ; null si les votes sont désactivés côté serveur. */
  feedback_token: string | null;
};

export const api = {
  /** Charge un document d'exemple présent côté serveur (dossier static/). */
  loadFile(fileName: string, sessionId: string) {
    return request("/api/load-file", {
      method: "POST",
      body: { file_name: fileName, session_id: sessionId },
    }).then((r) => parse<LoadFileResponse>(r));
  },

  /** Lance le pipeline complet (retrieval hybride + agents LangGraph). */
  processQuestion(question: string, sessionId: string) {
    return request("/api/process-question", {
      method: "POST",
      body: { question, session_id: sessionId },
    }).then((r) => parse<ProcessQuestionResponse>(r));
  },

  /** Texte OCR d'une page (numérotée à partir de 1) : le repli quand l'original n'est pas disponible. */
  pageText(fileHash: string, page: number, sessionId: string) {
    const query = new URLSearchParams({ file_hash: fileHash, page: String(page), session_id: sessionId });
    return request(`/api/documents/page?${query}`).then((r) => parse<PageTextResponse>(r));
  },

  /** Vote sur une réponse : 1 = satisfait, 0 = pas satisfait (commentaire facultatif). */
  sendFeedback(token: string, score: 0 | 1, sessionId: string, comment?: string) {
    return request("/api/feedback", {
      method: "POST",
      body: { feedback_token: token, score, comment, session_id: sessionId },
    }).then((r) => parse<{ message: string }>(r));
  },
};
