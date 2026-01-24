import { DocumentUploader } from "@/components/ui/document-uploader";
import { ExampleSelector } from "@/components/ui/example-selector";
import { QuestionInput } from "@/components/ui/question-input";
import { ResponseInputs } from "@/components/ui/reponses-inputs";
import ContactForm from "@/components/ui/contact-form";
import { Card, CardContent, CardTitle, CardHeader, CardDescription } from "@/components/ui/card.tsx";
import { useState, useCallback, useEffect, useRef } from "react";
import { api } from "./api";
import { useTimer } from "@/hooks/useTimer";

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
  const hasLoadedInitial = useRef(false);

  const hasDocument = selectedFile !== null || selectedExample !== null;
  const showDocumentUploader =
    selectedFile === null && selectedExample === null;

  useEffect(() => {
    const loadInitialExample = async () => {
      if (deepseekExample && !documentLoaded && !hasLoadedInitial.current) {
        hasLoadedInitial.current = true;
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
          <strong>RAG Multi-Agentique</strong> précis et à faible taux
          d'halucinations (5-1%)
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
      <Card
        id="contact-form"
        className="mt-12 border-none max-w-2xl mx-auto shadow-none"
      >
        <CardContent className="p-0 border-none">
          <CardTitle
            variant="h2"
            className="bg-gradient-to-br from-black via-black to-black bg-clip-text text-transparent"
          >
            Étude de cas
          </CardTitle>
          <CardTitle variant="h3-card" className="mb-0 mt-4">
            Le challenge
          </CardTitle>
          <CardTitle variant="h3" className="font-medium">
            Créer un système RAG récupérant de l'info factcheckée et pertinente
            dans le cas de docs techniques.
          </CardTitle>
          <ul className="list-disc list-inside mb-4 space-y-4">
            <li>
              <strong>Pertinence de la récupération</strong> : Remonter les
              passages exacts malgré le bruit, le vocabulaire technique et les
              tableaux.
            </li>
            <li>
              <strong>Avoir aussi un factcheck des réponses</strong> : Éviter
              les hallucinations et ne répondre qu'avec des preuves dans le
              contexte.
            </li>
            <li>
              <strong>Pouvoir couvrir de multiples documents et pages</strong> :
              Croiser plusieurs sources sans perdre l'information clé.
            </li>
            <li>
              <strong>
                Vérifier la qualité OCR avec la solution Mistral OCR
              </strong>{" "}
              : Extraire du texte propre depuis des PDF longs et hétérogènes.
            </li>
            <li>
              <strong>Évaluer la pertinence</strong> : Prouver la pertinence
              avec des métriques et des comparaisons avant/après.
            </li>
          </ul>
          <CardTitle variant="h3-card">Résultats et évaluation</CardTitle>
          <ul className="list-inside mb-4 space-y-4">
            <ul className="list-inside mb-4 space-y-4">
              <li>
                <strong>
                  Récupération hybride + ajout de 2 agents spécialisés
                  (FactChecker et PertinenceChecker)
                </strong>{" "}
                : La combinaison BM25 + recherche vectorielle permettant{" "}
                <span>
                  la bonne couverture et pertinence des réponses sur des
                  documentations techniques.
                </span>
              </li>
              <li>
                <strong>🌀 Ajout du reranker Cohere 3.5.</strong>
              </li>
              <li>
                <strong>🎯 Recall@10 (top 10 résultats) : 25% → 52.5%</strong> —{" "}
                <span>
                  donc 5 questions sur 8 ont au moins un passage pertinent dans
                  le top 10.
                </span>
              </li>
              <li>
                <strong>🎯 MRR@10 (top 10 résultats) : 24% → 85.6%</strong> —{" "}
                <span>
                  donc en moyenne le 1er bon passage arrive vers la 2ᵉ place.
                </span>
              </li>
              <li>
                <strong>🎯 nDCG@10 (top 10 résultats) : 22% → 69.5%</strong> —{" "}
                <span>
                  donc très bonnes performances globales de pertinence.
                </span>
              </li>
              <li>
                <strong>
                  <span>
                    🌀 7,5% d'hallucination grâce au mutli-agents de factchecking + le reranker Cohere 3.5
                  </span>
                </strong>
              </li>
              <li>
                <strong>
                  💡 Au final{" "}
                  <span>
                    81% des résponses jugées pertinentes d'après RAGAS,
                  </span>
                </strong>{" "}
                mais testé sur seulement 2 documents.
              </li>
            </ul>
          </ul>
          <img
            src="/static/langsmith.png"
            className="w-full h-auto rounded mt-3 border border-gray-100 rounded-sm"
          />
          <CardDescription className="italic text-center text-xs">
            Montoring dans Langsmith
          </CardDescription>
          <br />
          <p>
            En somme un bon POC.
            <br />
            Mais à améliorer pour passage à l'échelle.
          </p>
          <CardTitle
            variant="h3"
            className="mt-12 max-w-xl mx-auto text-center"
          >
            On discute de votre projet d'automatisation ou d'application?
          </CardTitle>
          <CardDescription className="text-center mb-4">
            Remplissez le formulaire ci-dessous et je vous recontacte dans les
            24-48 heures.
          </CardDescription>
          <ContactForm />
        </CardContent>
      </Card>
    </main>
  );
};
