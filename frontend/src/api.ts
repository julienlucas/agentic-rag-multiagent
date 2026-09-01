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
export type ProcessQuestionResponse = { draft_answer: string; verification_report: string };

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
};
