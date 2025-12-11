const API_BASE_URL = "http://localhost:8000";

class ApiService {
  async loadFile(fileName: string, sessionId: string = "default") {
    try {
      const response = await fetch(`${API_BASE_URL}/load-file`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ file_name: fileName, session_id: sessionId }),
      });

      const data = await response.json();
      return { data };
    } catch (error) {
      return {
        error:
          error instanceof Error ? error.message : "Erreur de connexion",
      };
    }
  }

  async uploadFile(
    file: File,
    sessionId: string
  ) {
    const formData = new FormData();
    formData.append("session_id", sessionId);
    formData.append("file", file);

    try {
      const response = await fetch(`${API_BASE_URL}/upload-file`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      return { data };
    } catch (error) {
      return {
        error: error instanceof Error ? error.message : "Erreur de connexion",
      };
    }
  }

  async processQuestion(
    question: string,
    sessionId: string
  ) {
    try {
      const response = await fetch(`${API_BASE_URL}/process-question`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question, session_id: sessionId }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return { data };
    } catch (error) {
      return {
        error: error instanceof Error ? error.message : "Erreur de connexion",
      };
    }
  }
}

export const api = new ApiService();
