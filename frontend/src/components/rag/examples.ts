import type { Citation } from "@/api";

export type Evidence = { src: string; caption: string };

export type ExampleQuestion = {
  text: string;
  hint: string;
  evidence?: Evidence[];
};

export type ExampleDoc = {
  id: string;
  title: string;
  fileName: string;
  kind: "PDF";
  pages: number;
  type: string;
  description: string;
  questions: ExampleQuestion[];
};

/*
 * Deux rapports annuels du benchmark FinanceBench (Patronus AI) : leurs questions ont une
 * réponse de référence annotée par des experts, avec la page de la preuve.
 */
export const exampleDocs: ExampleDoc[] = [
  {
    id: "amd-2022",
    title: "AMD · rapport annuel 10-K 2022",
    fileName: "AMD_2022_10K.pdf",
    kind: "PDF",
    pages: 121,
    type: "Rapport annuel (SEC)",
    description:
      "121 pages d'états financiers : bilan, compte de résultat par segment, chaque chiffre répété sur plusieurs exercices.",
    questions: [
      {
        text: "AMD a-t-elle un profil de liquidité sain d'après son quick ratio de l'exercice 2022 ?",
        hint: "Calcul d'un ratio à partir du bilan · référence : 1,57 (p. 56)",
      },
      {
        text: "Entre 2021 et 2022, hors Embedded, quel segment d'AMD a le plus progressé en proportion de ses ventes ?",
        hint: "Lecture croisée d'un tableau par segment · référence : Data Center (p. 48)",
      },
      {
        text: "AMD signale-t-elle une concentration de clients sur l'exercice 2022 ?",
        hint: "Information enfouie dans le texte · référence : un client = 16 % du CA (p. 12)",
      },
    ],
  },
  {
    id: "boeing-2022",
    title: "Boeing · rapport annuel 10-K 2022",
    fileName: "BOEING_2022_10K.pdf",
    kind: "PDF",
    pages: 190,
    type: "Rapport annuel (SEC)",
    description:
      "190 pages : activités par division, litiges, notes fiscales, avec des valeurs proches d'un exercice à l'autre.",
    questions: [
      {
        text: "Comment le taux d'imposition effectif de Boeing en 2022 se compare-t-il à celui de 2021 ?",
        hint: "Deux exercices dans le même tableau · référence : 0,62 % contre −14,76 % (p. 55)",
      },
      {
        text: "Boeing fait-elle face à des procédures judiciaires importantes en cours sur l'exercice 2022 ?",
        hint: "Note aux états financiers · référence : accidents Lion Air et Ethiopian Airlines (p. 113)",
      },
      {
        text: "Quelles évolutions de cadence de production Boeing prévoit-elle pour 2023 ?",
        hint: "Perspectives de la direction · référence : hausse pour les 737, 777X et 787 (p. 9)",
      },
    ],
  },
];

export const SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md"];
export const MAX_FILE_MB = 50;

/**
 * Sortie réelle du pipeline sur le rapport AMD pré-chargé (11 oct. 2026), affichée comme exemple
 * tant qu'aucune question n'est posée. Seule retouche : la phrase de transition de l'agent en tête
 * de réponse est retirée. Le quick ratio obtenu (1,57) est la réponse de référence de FinanceBench ;
 * la citation [11] rouvre le bilan consolidé, page 56.
 */
export const exampleOutput = {
  docId: "amd-2022",
  question: "AMD a-t-elle un profil de liquidité sain d'après son quick ratio de l'exercice 2022 ?",
  elapsed: 14,
  answer: `## Calcul du Quick Ratio d'AMD – Exercice 2022

Le quick ratio (ou « acid-test ratio ») mesure la capacité d'une entreprise à honorer ses passifs courants avec ses actifs les plus liquides, **en excluant les stocks et les charges payées d'avance**.

**Formule :**
> **Quick Ratio = (Trésorerie + Placements à court terme + Créances clients) / Passifs courants**

**Données issues du bilan consolidé au 31 décembre 2022** [11] :

| Composante | Montant (M$) |
|---|---|
| Cash and cash equivalents | 4 835 |
| Short-term investments | 1 020 |
| Accounts receivable, net | 4 126 |
| Receivables from related parties | 2 |
| **Total actifs rapides** | **9 983** |
| **Total current liabilities** | **6 369** |

*(Exclusions : Inventories = 3 771 M$ et Prepaid expenses and other current assets = 1 265 M$)* [11]

**Calcul :**
> Quick Ratio = 9 983 / 6 369 ≈ **1,57**

---

## Interprétation

Avec un quick ratio de **~1,57**, AMD présente un **profil de liquidité sain** pour l'exercice 2022 [11] :

- Un quick ratio **supérieur à 1,0** signifie que l'entreprise dispose de suffisamment d'actifs liquides pour couvrir l'intégralité de ses passifs courants sans avoir à liquider ses stocks ni ses charges prépayées.
- Le ratio de **1,57** indique qu'AMD possède **1,57 $ d'actifs quasi-liquides pour chaque dollar de dette à court terme**, ce qui reflète une position de liquidité confortable.
- Cette solidité est notamment soutenue par un niveau de trésorerie et placements à court terme élevé (4 835 + 1 020 = **5 855 M$**) et des créances clients significatives (**4 126 M$**) [11].

En conclusion, d'après son quick ratio de 2022, AMD affiche une **liquidité solide et rassurante**.`,
  report: `**Pertinent:** Oui
**Pertinence des passages:** PARTIAL — couverture partielle — la réponse peut être incomplète
**Confiance retrieval (reranker):** 0.58 — moyenne
**Recherche corrective:** déclenchée (2 appels d'outils)
  • *navigate: "consolidated balance sheet" [AMD_2022_10K]*
  • *read_page: AMD_2022_10K p. 56*
**Sources utilisées:** AMD_2022_10K (p. 4, 42, 43, 56, 93, 96…) — 11 passages transmis au modèle`,
  citations: [
    {
      n: 11,
      source: "AMD_2022_10K",
      page: 56,
      locator: "AMD_2022_10K, p. 56",
      excerpt: "Table of Contents # Advanced Micro Devices, Inc. # Consolidated Balance Sheets | | December 31, 2022 | December 25, 2021 | | --- | --- | --- | | | (In millions, except par value amounts) | | | **ASSETS** | | | | **Current assets:** | | | | Cash and cash equivalents | $ 4,835 | $ ",
      file_hash: "a3bd74088fae0ad4aa03d04998a1f4c64fd0b3c693841601b0ac49b46cf5c1f4",
      pdf_url: "/static/AMD_2022_10K.pdf",
      text: `Table of Contents

# Advanced Micro Devices, Inc.

# Consolidated Balance Sheets

|   | December 31, 2022 | December 25, 2021  |
| --- | --- | --- |
|   | (In millions, except par value amounts)  |   |
|  **ASSETS**  |   |   |
|  **Current assets:**  |   |   |
|  Cash and cash equivalents | $ 4,835 | $ 2,535  |
|  Short-term investments | 1,020 | 1,073  |
|  Accounts receivable, net | 4,126 | 2,706  |
|  Inventories | 3,771 | 1,955  |
|  Receivables from related parties | 2 | 2  |
|  Prepaid expenses and other current assets | 1,265 | 312  |
|  **Total current assets** | **15,019** | **8,583**  |
|  Property and equipment, net | 1,513 | 702  |
|  Operating lease right-of-use assets | 460 | 367  |
|  Goodwill | 24,177 | 289  |
|  Acquisition-related intangibles | 24,118 | —  |
|  Investment: equity method | 83 | 69  |
|  Deferred tax assets | 58 | 931  |
|  Other non-current assets | 2,152 | 1,478  |
|  **Total assets** | **$ 67,580** | **$ 12,419**  |
|  **LIABILITIES AND STOCKHOLDERS' EQUITY**  |   |   |
|  **Current liabilities:**  |   |   |
|  Accounts payable | $ 2,493 | $ 1,321  |
|  Payables to related parties | 463 | 85  |
|  Accrued liabilities | 3,077 | 2,424  |
|  Current portion of long-term debt, net | — | 312  |
|  Other current liabilities | 336 | 98  |
|  **Total current liabilities** | **6,369** | **4,240**  |
|  Long-term debt, net of current portion | 2,467 | 1  |
|  Long-term operating lease liabilities | 396 | 348  |
|  Deferred tax liabilities | 1,934 | 12  |
|  Other long-term liabilities | 1,664 | 321  |
|  Commitments and Contingencies (see Notes 16 and 17) |  |   |
|  **Stockholders' equity:**  |   |   |
|  Capital stock: |  |   |
|  Common stock, par value $0.01; shares authorized: 2,250; shares issued: 1,645 and 1,232; shares outstanding: 1,612 and 1,207 | 16 | 12  |
|  Additional paid-in capital | 58,005 | 11,069  |
|  Treasury stock, at cost (shares held: 33 and 25) | (3,099) | (2,130)  |
|  Accumulated deficit | (131) | (1,451)  |
|  Accumulated other comprehensive loss | (41) | (3)  |
|  **Total stockholders' equity** | **54,750** | **7,497**  |
|  **Total liabilities and stockholders' equity** | **$ 67,580** | **$ 12,419**  |

See accompanying notes to consolidated financial statements.

53`,
    },
  ] satisfies Citation[],
};
