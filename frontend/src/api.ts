const API_URL = import.meta.env.VITE_RAILWAY_API_URL || "";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function parse<T>(response: Response): Promise<T> {
  let data: any = null;
  try {
    data = await response.json();
  } catch {
    /* corps vide */
  }
  if (!response.ok || data?.error) {
    throw new ApiError(data?.error || `Erreur serveur (${response.status})`, response.status);
  }
  return data as T;
}

export type LoadFileResponse = { message: string; chunks_count: number; filename: string };
export type UploadFileResponse = { message: string; chunks_count: number };
export type Citation = {
  n: number;
  source: string;
  page: number | null;
  locator: string;
  excerpt: string;
  /** De quoi rouvrir le document au passage cité (absents des réponses antérieures). */
  file_hash?: string | null;
  /** Original du document : /static/… pour un exemple, /api/documents/…/file pour un dépôt. */
  pdf_url?: string | null;
  /** Passage entier transmis au modèle, pour le surligner dans la page. */
  text?: string;
};

export type PageTextResponse = { file_hash: string; page: number; text: string };

/** URL de l'original : l'API sert les fichiers déposés (contrôle par espace), le frontend les exemples. */
export function documentUrl(pdfUrl: string, sessionId: string): string {
  if (pdfUrl.startsWith("/api/")) return `${API_URL}${pdfUrl}?session_id=${encodeURIComponent(sessionId)}`;
  return pdfUrl;
}

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
    return fetch(`${API_URL}/api/load-file`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_name: fileName, session_id: sessionId }),
    }).then((r) => parse<LoadFileResponse>(r));
  },

  /** Upload + OCR + indexation d'un document utilisateur. */
  uploadFile(file: File, sessionId: string) {
    const formData = new FormData();
    formData.append("session_id", sessionId);
    formData.append("file", file);
    return fetch(`${API_URL}/api/upload-file`, { method: "POST", body: formData }).then((r) =>
      parse<UploadFileResponse>(r),
    );
  },

  /** Lance le pipeline complet (retrieval hybride + agents LangGraph). */
  processQuestion(question: string, sessionId: string) {
    return fetch(`${API_URL}/api/process-question`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, session_id: sessionId }),
    }).then((r) => parse<ProcessQuestionResponse>(r));
  },

  /** Texte OCR d'une page (numérotée à partir de 1) : le repli quand l'original n'est pas disponible. */
  pageText(fileHash: string, page: number, sessionId: string) {
    const query = new URLSearchParams({ file_hash: fileHash, page: String(page), session_id: sessionId });
    return fetch(`${API_URL}/api/documents/page?${query}`).then((r) => parse<PageTextResponse>(r));
  },

  /** Vote sur une réponse : 1 = satisfait, 0 = pas satisfait (commentaire facultatif). */
  sendFeedback(token: string, score: 0 | 1, sessionId: string, comment?: string) {
    return fetch(`${API_URL}/api/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ feedback_token: token, score, comment, session_id: sessionId }),
    }).then((r) => parse<{ message: string }>(r));
  },
};
