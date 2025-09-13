class ApiService {
  async loadFile(fileName: string, sessionId: string = "default") {
    try {
      const response = await fetch("load-file", {
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
      const response = await fetch("upload-file", {
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
    const response = await fetch("process-question", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ question, session_id: sessionId }),
    });

    const data = await response.json();
    return { data };
  }
}

export const api = new ApiService();
