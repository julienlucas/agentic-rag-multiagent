import { DocumentUploader } from "@/components/ui/document-uploader";
import { ExampleSelector } from "@/components/ui/example-selector";
import { QuestionInput } from "@/components/ui/question-input";
import { ResponseInputs } from "@/components/ui/reponses-inputs";
import { Card, CardContent, CardTitle, CardHeader, CardDescription } from "@/components/ui/card.tsx";
import { Button } from "@/components/ui/button";
import { useState, useCallback, useEffect } from "react";
import { api } from "./api";

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

export default function Index() {
  const deepseekExample = examples.find(ex => ex.id === "deepseek-r1");

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedExample, setSelectedExample] = useState<any | null>(deepseekExample || null);
  const [answer, setAnswer] = useState<string>("");
  const [verificationReport, setVerificationReport] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [documentLoaded, setDocumentLoaded] = useState(false);
  const [sessionId] = useState(() => `session_${Date.now()}`);
  const [isLoadingExample, setIsLoadingExample] = useState(false);
  const [preloadedQuestion, setPreloadedQuestion] = useState<string>(deepseekExample?.question || "");

  const hasDocument = selectedFile !== null || selectedExample !== null;
  const showDocumentUploader =
    selectedFile === null && selectedExample === null;

  useEffect(() => {
    const loadInitialExample = async () => {
      if (deepseekExample && !documentLoaded) {
        setIsLoadingExample(true);
        try {
          const response = await api.loadFile(
            deepseekExample.file_paths?.[0] || "",
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
      }
    };
    loadInitialExample();
  }, []);

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
        await api.uploadFile(selectedFile, sessionId);
        setDocumentLoaded(true);
        return;
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
      title: file.name.replace(/\.[^/.]+$/, ""),
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
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
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
        setVerificationReport(
          convertMarkdownToHtml(response.data.verification_report)
        );
      }
    } catch (error) {
      console.error(error);
      setAnswer("Erreur lors du traitement de la question");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="mx-auto max-w-5xl w-full pb-24 px-2">
      <CardHeader className="relative z-20">
        <CardTitle
          variant="h1"
          className="text-center mx-auto max-w-sm flex items-center justify-center gap-3"
        >
          <div
            style={{ fontFamily: "'Gabarito', sans-serif" }}
            className="font-bold bg-gradient-to-br from-[#36e3ac] via-[#62eec2] to-[#b2f7e1] text-[#30574a] rounded-xl w-11 h-11 flex items-center justify-center text-4xl"
          >
            S
          </div>
          <span style={{ fontFamily: "'Gabarito', sans-serif" }}>DocChat</span>
        </CardTitle>
        <CardDescription className="text-center text-2xl font-bold text-black max-w-xl mx-auto leading-7">
          Trouvez l'info pertinente et sans hallucinations dans vos docs
          techniques
        </CardDescription>
        <CardDescription className="text-center text-sm">
          <strong>RAG Agentique</strong> précis et à faible taux d'halucinations
          (5-1%)
          <br />
          fonctionne avec 3 modèles Mistral AI (Embbed, OCR et Mistral Large)
        </CardDescription>
        <img
          src="/static/mistral.png"
          alt=""
          className="object-contain mx-auto flex justify-center mx-auto border border-gray-100 rounded-xl w-10 h-10 p-1 shadow-lg"
        />
      </CardHeader>
      <Card className="border-none shadow-none">
        <CardContent className="p-0">
          <div className="container mx-auto px-0 w-full">
            <div className="grid lg:grid-cols-2 gap-8">
              <div className="space-y-8">
                <ExampleSelector
                  onExampleSelect={handleExampleSelect}
                  selectedExample={selectedExample}
                  examples={examples}
                  onLoadExample={handleLoadExample}
                  onRemoveExample={handleRemoveExample}
                  isLoading={isLoadingExample}
                  documentLoaded={documentLoaded}
                />
                {showDocumentUploader && (
                  <DocumentUploader
                    onUploadFile={handleFileSelect}
                    selectedFile={selectedFile}
                    isUploading={isLoadingExample}
                  />
                )}
                <QuestionInput
                  hasDocument={hasDocument}
                  isLoading={isLoading}
                  documentLoaded={documentLoaded}
                  onQuestionSubmit={handleQuestionSubmit}
                  preloadedQuestion={preloadedQuestion}
                />
              </div>
              <div className="lg:sticky lg:top-8">
                <ResponseInputs
                  answer={answer}
                  verificationReport={verificationReport}
                  isLoading={isLoading}
                />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
      <Card className="mt-12 border-none max-w-2xl mx-auto shadow-none">
        <CardContent className="p-0 border-none">
          <CardTitle
            variant="h2"
            className="bg-gradient-to-br from-black via-black to-black bg-clip-text text-transparent"
          >
            Étude de cas
          </CardTitle>
          <CardTitle variant="h3">....</CardTitle>
          <CardTitle variant="h3">Le challenge</CardTitle>
          <p className="mb-4">
            Créer un système RAG (Retrieval-Augmented Generation) capable de
            répondre précisément aux questions sur des documents techniques tout
            en minimisant les hallucinations. Les défis principaux étaient :
          </p>
          <ul className="list-disc list-inside mb-4 space-y-2">
            <li>
              <strong>Réduction des hallucinations</strong> : Les modèles LLM
              génèrent souvent des informations non présentes dans les documents
              sources
            </li>
            <li>
              <strong>Vérification factuelle</strong> : S'assurer que chaque
              réponse est directement supportée par le contexte fourni
            </li>
            <li>
              <strong>Récupération hybride</strong> : Combiner recherche
              sémantique (vecteurs) et recherche lexicale (BM25) pour une
              meilleure précision
            </li>
            <li>
              <strong>Orchestration multi-agents</strong> : Coordonner plusieurs
              agents spécialisés (recherche, vérification, pertinence) pour une
              réponse optimale
            </li>
            <li>
              <strong>Traitement OCR</strong> : Extraire et traiter efficacement
              le texte depuis des documents PDF techniques
            </li>
          </ul>
          <CardTitle variant="h3">Résultats et évaluation</CardTitle>
          <p className="mb-4">
            Le système utilise une approche de transfer learning avec
            MobileNetV3 Large pour détecter les images générées par IA :
          </p>
          <ul className="list-inside mb-4 space-y-2">
            <ul className="list-disc list-inside mb-4 space-y-2">
              <li>
                <strong>Architecture multi-agents</strong> : Orchestration avec
                LangGraph de 3 agents spécialisés (recherche, vérification,
                pertinence)
              </li>
              <li>
                <strong>Fact-checker intégré</strong> : Chaque réponse est
                automatiquement vérifiée contre les documents sources avant
                d'être retournée
              </li>
              <li>
                <strong>Récupération hybride</strong> : Combinaison BM25 (40%) +
                recherche vectorielle (60%) pour une meilleure couverture
              </li>
              <li>
                <strong>Traitement OCR avancé</strong> : Utilisation de Mistral
                OCR pour extraire le texte depuis les PDF techniques
              </li>
              <li>
                <strong>Réduction des hallucinations</strong> : Le système
                refuse de répondre si les documents ne contiennent pas
                d'informations pertinentes
              </li>
            </ul>
          </ul>
          <img
            src="/static/langsmith.png"
            alt="border border-gray-100 rounded-xl w-full"
          />
          <CardDescription className="italic text-center text-xs">
            Montoring dans Langsmith
          </CardDescription>
          <p>Et voilà.</p>
          <CardTitle variant="h3" className="mt-6 text-center">
            On discute de votre projet?
          </CardTitle>
          <div className="flex justify-center">
            <Button className="mx-auto w-full" size="xl">
              Me contacter
            </Button>
          </div>
        </CardContent>
      </Card>
    </main>
  );
};
