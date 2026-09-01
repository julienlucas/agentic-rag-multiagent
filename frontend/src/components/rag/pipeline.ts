/**
 * Étapes du pipeline telles qu'implémentées côté backend
 * (retriever/builder.py + agents/workflow.py + config/settings.py).
 * Les durées servent uniquement à animer la trace pendant l'attente :
 * le backend ne streame pas, les signaux réels arrivent avec la réponse.
 */
export type PipelineStep = {
  key: "route" | "retrieve" | "rerank" | "check" | "correct" | "research";
  label: string;
  detail: string;
  model?: string;
  conditional?: boolean;
  ms: number;
};

export const pipelineSteps: PipelineStep[] = [
  {
    key: "route",
    label: "Routage & réécriture",
    detail:
      "Cible le document visé par la question, puis génère une reformulation (multi-query) pour élargir le rappel.",
    model: "mistral-small",
    ms: 1400,
  },
  {
    key: "retrieve",
    label: "Recherche hybride",
    detail:
      "BM25 (k = 20) + vecteurs Chroma / mistral-embed (k = 20), fusion RRF 0,5 / 0,5, puis remontée des chunks parents (1 200 car.).",
    model: "mistral-embed",
    ms: 1800,
  },
  {
    key: "rerank",
    label: "Reranking Cohere",
    detail: "rerank-v4.0-pro sur ≤ 40 candidats → 30 passages scorés.",
    model: "cohere rerank-v4",
    ms: 1600,
  },
  {
    key: "check",
    label: "Agent vérificateur de pertinence",
    detail: "Classe les 3 meilleurs passages : CAN_ANSWER, PARTIAL ou NO_MATCH.",
    model: "mistral-small",
    ms: 2200,
  },
  {
    key: "correct",
    label: "Recherche corrective",
    detail:
      "Déclenchée si NO_MATCH ou score reranker max < 0,50 : 3 requêtes réécrites dans le lexique du document, top 5 protégé, 1 tour max.",
    model: "mistral-small",
    conditional: true,
    ms: 0,
  },
  {
    key: "research",
    label: "Agent de recherche",
    detail:
      "Rédige la réponse, contraint aux 10 meilleurs passages — refuse explicitement si la preuve est absente.",
    model: "mistral-large",
    ms: 0,
  },
];
