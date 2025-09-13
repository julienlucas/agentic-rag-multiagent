import { DocumentUploader } from "@/components/ui/document-uploader";
import { ExampleSelector } from "@/components/ui/example-selector";
import { QuestionInput } from "@/components/ui/question-input";
import { ResponseInputs } from "@/components/ui/reponses-inputs";
import { useState, useCallback } from "react";
import { api } from "../api";

const examples = [
  {
    id: "google-env-2024",
    title: "Rapport Environnemental Google 2024",
    question:
      "Récupère les valeurs d'efficacité PUE du centre de données dans l'installation 2 de Singapour en 2019 et 2022. Récupére également la moyenne régionale CFE en Asie-Pacifique en 2023",
    file_paths: ["google-2024-environmental-report.pdf"],
    description:
      "Rapport annuel sur les initiatives environnementales de Google",
    type: "Rapport Environnemental",
  },
  {
    id: "deepseek-r1",
    title: "Rapport Technique DeepSeek-R1",
    question:
      "Résume l'évaluation des performances du modèle DeepSeek-R1 sur toutes les tâches de codage par rapport au modèle OpenAI o1-mini",
    file_paths: ["DeepSeek Technical Report.pdf"],
    description: "Documentation technique du modèle DeepSeek-R1",
    type: "Rapport Technique",
  },
];

export const Dashboard = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedExample, setSelectedExample] = useState<any | null>(null);
  const [answer, setAnswer] = useState<string>("");
  const [verificationReport, setVerificationReport] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [documentLoaded, setDocumentLoaded] = useState(false);
  const [sessionId] = useState(() => `session_${Date.now()}`);
  const [isLoadingExample, setIsLoadingExample] = useState(false);
  const [preloadedQuestion, setPreloadedQuestion] = useState<string>("");

  const hasDocument = selectedFile !== null || selectedExample !== null;
  const showDocumentUploader = selectedFile === null && selectedExample === null;

  const handleExampleSelect = (example) => {
    setSelectedExample(example);
    setPreloadedQuestion(example.question || "");
  };

  const handleRemoveExample = () => {
    setDocumentLoaded(false);
    setSelectedExample(null);
    setPreloadedQuestion("");
    setSelectedFile(null);
  };

  const handleLoadExample = async () => {
    setIsLoadingExample(true);
    try {
      if (selectedFile) {
        await api.uploadFile(
          selectedFile,
          sessionId
        );
        setDocumentLoaded(true);
        return
      }
      const response = await api.loadFile(
        selectedExample.file_paths?.[0] || "",
        sessionId
      );
      const file = new File([], response.data.filename, {
        type: response.data.file_type,
      });
      setDocumentLoaded(true);
      setSelectedFile(file);
    } catch (error) {
      console.error("Erreur lors du chargement de l'exemple:", error);
    } finally {
      setIsLoadingExample(false);
    }
  };

  const handleFileSelect = (file: File | null) => {
    setSelectedFile(file);
    setSelectedExample({
      title: file.name.replace(/\.[^/.]+$/, "")
    });

    // Si on upload un fichier, on efface la question préchargée de l'exemple
    if (file) {
      setPreloadedQuestion("");
    } else if (!file && selectedExample) {
      // Si on retire le fichier et qu'un exemple est sélectionné, on recharge sa question
      setPreloadedQuestion(selectedExample.question || "");
      setDocumentLoaded(false);
    }
  };

  const convertMarkdownToHtml = useCallback((text) => {
    return text
      .replace(/### (.*?)(?=\n|$|###|##)/g, '<h3 class="mt-2 -mb-3">$1</h3>')
      .replace(/## (.*?)(?=\n|$|###|##)/g, '<h3 class="mt-2 -mb-3">$1</h3>')
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
  }, []);

  // Gestion des questions
  const handleQuestionSubmit = async (question: string) => {
    if (!question.trim() || !hasDocument) return;

    console.log("Processing question with sessionId:", sessionId);
    setIsLoading(true);
    setAnswer("");
    setVerificationReport("");

    try {
      const response = await api.processQuestion(question, sessionId);
      if (response.data) {

        setAnswer(convertMarkdownToHtml(response.data.draft_answer));
        setVerificationReport(convertMarkdownToHtml(response.data.verification_report));
      }
    } catch (error) {
      console.error(error);
      setAnswer("Erreur lors du traitement de la question");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="mb-6">
      <div className="text-center space-y-6 animate-fade-in">
        <div>
          <p className="max-w-3xl mx-auto text-4xl text-muted-foreground">
            <span className="font-medium text-foreground">
              RAG Agentique multiagent avec fact-checking propulsé par
            </span>{" "}
            <span>Mistral OCR 🤖</span>{" "}
            <span className="text-muted-foreground">et</span>{" "}
            <span>LangGraph</span>
          </p>
        </div>

        <div className="w-full max-w-3xl mx-auto space-y-2 text-muted-foreground">
          <p className="flex items-center gap-2">
            <span className="text-primary">📄</span>
            Téléchargez vos documents, entrez votre question puis cliquez sur
            Envoyer
          </p>
          <p className="gap-2">
            <span className="text-primary">💡</span>
            Ou sélectionnez un des exemples dans le menu déroulant, cliquez sur
            charger le fichier puis envoyer
          </p>
          <div className="bg-[#e3fbf3] rounded-lg p-3 mt-4 w-fit mx-auto">
            <p className="text-sm flex items-center gap-2">
              {/* <span className="text-warning">⚠️</span> */}
              <span className="font-medium">Note:</span>
              DocChat n'accepte que les documents aux formats: '.pdf', '.docx',
              '.txt', '.md'
            </p>
          </div>
        </div>
      </div>

      {/* Onboarding pour nouveaux utilisateurs */}
      <div className="container mx-auto px-4 py-8 w-full">
        {/* Main Content */}
        <div className="mt-16 grid lg:grid-cols-2 gap-8">
          {/* Left Panel - Upload & Examples */}
          <div className="space-y-8">
            {/* Example Selector */}
            <ExampleSelector
              onExampleSelect={handleExampleSelect}
              selectedExample={selectedExample}
              examples={examples}
              onLoadExample={handleLoadExample}
              onRemoveExample={handleRemoveExample}
              isLoading={isLoadingExample}
              documentLoaded={documentLoaded}
            />

            {/* Document Uploader */}
            {showDocumentUploader && (
              <DocumentUploader
                onUploadFile={handleFileSelect}
                selectedFile={selectedFile}
                isUploading={isLoadingExample}
              />
            )}

            {/* Question Input */}
            <QuestionInput
              hasDocument={hasDocument}
              isLoading={isLoading}
              documentLoaded={documentLoaded}
              onQuestionSubmit={handleQuestionSubmit}
              preloadedQuestion={preloadedQuestion}
            />
          </div>

          {/* Right Panel - Chat Interface */}
          <div className="lg:sticky lg:top-8">
            <ResponseInputs
              answer={answer}
              verificationReport={verificationReport}
              isLoading={isLoading}
            />
          </div>
        </div>
      </div>
    </div>
  );
};
