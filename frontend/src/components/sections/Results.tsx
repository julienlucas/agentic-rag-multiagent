import { useState, type CSSProperties } from "react";
import { Table2 } from "lucide-react";
import { Section } from "@/components/site/primitives";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/*
 * Chiffres : expériences LangSmith du dataset FinanceBench, 12 oct. 2026, juge Qwen3 235B calibré
 * sur annotation humaine, modèle de réponse Claude Sonnet 4.6 (Bedrock).
 * - Corpus complet : « … · agentic · 2026-10-12 14:26 », 84 rapports, 139 questions, 135 jugées
 *   (4 bloquées par le quota quotidien de tokens Bedrock, non comptées).
 * - Pilote : « … · agentic · 2026-10-12 13:46 », 20 rapports, 65 questions.
 * - Sans outils : « … · baseline · 2026-10-12 13:16 », pilote de 20 rapports, 65 questions — le seul
 *   témoin sans outils mesuré sur le code actuel (pas encore sur les 84 rapports).
 * Le niveau « RAG naïf » est le chiffre publié dans le papier FinanceBench (Islam et al., 2023)
 * pour un RAG naïf sur vector store partagé, sur le benchmark complet.
 */
const levels = [
  {
    label: "RAG naïf",
    setup:
      "Vector store partagé, sans agents · chiffre du papier FinanceBench, benchmark complet",
    correct: "~19 %",
    wrong: "81 % de réponses fausses ou refusées",
    tone: "muted" as const,
  },
  {
    label: "Ce RAG, sans outils de navigation · Claude Sonnet 4.6",
    setup:
      "Même index, même retrieval, mêmes 10 passages initiaux, même modèle : une seule génération, sans search / grep / read_page. Le témoin qui mesure ce que les outils apportent, mesuré sur le pilote de 20 rapports.",
    correct: "53,8 %",
    wrong: "35 bonnes réponses sur 65 questions (20 rapports)",
    tone: "plain" as const,
  },
  {
    label: "Ce RAG, avec outils de navigation · Claude Sonnet 4.6",
    setup:
      "Modèle de réponse : Claude Sonnet 4.6 (Bedrock), Claude Haiku 4.5 pour les sous-agents · hybride BM25 + vecteurs · routage · reranking Cohere · vérificateur de pertinence · agent de recherche à outils (search / grep / read_page / navigate / open) · génération contrainte aux preuves",
    correct: "88,1 %",
    wrong: "119 bonnes réponses sur 135 questions, 84 rapports, 12 000 pages indexées ensemble · 92,3 % sur le pilote de 20 rapports (60 sur 65, 3 048 pages)",
    tone: "brand" as const,
  },
];

type Row = {
  metric: string;
  before: number;
  noTools: number;
  after: number;
  hint: string;
  lowerIsBetter?: boolean;
};

const rows: Row[] = [
  {
    metric: "Correctes",
    before: 19,
    noTools: 53.8,
    after: 88.1,
    hint: "verdict CORRECT du juge LLM · avec outils de navigation : 119 sur 135, 84 rapports · sans : 35 sur 65, pilote de 20 rapports",
  },
  {
    metric: "Fausses ou refusées",
    before: 81,
    noTools: 46.2,
    after: 11.9,
    hint: "avec outils de navigation : 11,1 % d'hallucinations + 0,7 % de refus · sans : 46,2 % (23,1 % d'hallucinations + 23,1 % de refus) · plus bas = mieux",
    lowerIsBetter: true,
  },
];

const levers = [
  {
    title: "Un agent de recherche avec des outils",
    text: "Le modèle de réponse cherche lui-même avec search (hybride + rerank), grep (occurrences page par page), navigate / open_doc (le plan du rapport) et read_page (la page entière, tableau compris, 1 à 3 pages), 5 appels au plus, et répond dans la même conversation. Sur les 84 rapports : recherche lancée sur 64 % des questions, 2,6 appels en moyenne, une page entière lue dans 84 % des cas.",
  },
  {
    title: "Reranking Cohere",
    text: "40 candidats rescorés, 30 conservés : les distracteurs sortent du top. Le plus gros gain côté retrieval.",
  },
  {
    title: "Recherche hybride + routage",
    text: "BM25 et vecteurs fusionnés par RRF, un routeur qui cible le bon document avant de chercher.",
  },
  {
    title: "Texte recalé page par page",
    text: "Le markdown OCR des 84 rapports (~12 000 pages) est recalé sur les pages du PDF : les tableaux d'un 10-K survivent, et chaque chunk garde sa page. Un document aux tableaux corrompus est repassé à l'OCR.",
  },
  {
    title: "Génération contrainte",
    text: "Le modèle de réponse ne répond qu'à partir des passages retenus et refuse quand la preuve manque — sauf pour calculer un ratio dont les composantes sont sous ses yeux, formule et chiffres cités.",
  },
  {
    title: "Chunking parent / enfant",
    text: "Petits chunks (400 car.) pour matcher, parents (1 200 car.) transmis au modèle pour répondre avec le contexte.",
  },
  {
    title: "Agent vérificateur de pertinence",
    text: "Les passages sont classés CAN_ANSWER / PARTIAL / NO_MATCH avant génération. Le verdict est transmis au modèle de réponse comme indice : sur PARTIAL ou NO_MATCH, il sait qu'il doit chercher.",
  },
];

/*
 * Métriques détaillées du run avec outils de navigation sur le corpus complet de 84 rapports
 * (12 oct. 2026, 14:26).
 */
type MetricRow = { metric: string; full: string; hint: string };

const metricGroups: { title: string; rows: MetricRow[] }[] = [
  {
    title: "Retrieval (passages initiaux, avant les outils)",
    rows: [
      {
        metric: "page_hit@5 · @20",
        full: "58,5 · 70,4 %",
        hint: "part des questions dont une page de preuve est dans les k premiers passages",
      },
      {
        metric: "recall@20 (texte)",
        full: "72,6 %",
        hint: "part des passages de preuve retrouvés dans les 20 premiers",
      },
      {
        metric: "precision@5 (texte)",
        full: "36,3 %",
        hint: "part des 5 premiers passages issus d'une page de preuve · plafonnée : 1 à 2 pages de preuve par question",
      },
    ],
  },
  {
    title: "Agent",
    rows: [
      {
        metric: "Recherche lancée",
        full: "63,7 %",
        hint: "part des questions où l'agent appelle au moins un outil",
      },
      {
        metric: "Appels d'outils",
        full: "2,6",
        hint: "en moyenne, quand l'agent cherche (5 au plus)",
      },
      {
        metric: "Preuve transmise au modèle",
        full: "88,9 %",
        hint: "la page de preuve annotée atteint le modèle, outils compris",
      },
    ],
  },
  {
    title: "Réponse",
    rows: [
      {
        metric: "Correctes",
        full: "88,1 % (119)",
        hint: "verdict CORRECT du juge LLM · 135 questions jugées",
      },
      {
        metric: "Hallucinations",
        full: "11,1 % (15)",
        hint: "réponse affirmée mais fausse",
      },
      {
        metric: "Refus",
        full: "0,7 % (1)",
        hint: "",
      },
      {
        metric: "Faithfulness",
        full: "4,85 / 5",
        hint: "la réponse s'en tient aux extraits · note du juge LLM",
      },
      {
        metric: "Answer relevancy",
        full: "0,62",
        hint: "la réponse traite la question posée · méthode RAGAS, 0 à 1",
      },
    ],
  },
];

function MetricsTable() {
  return (
    <figure className="card-paper border-hairline mt-14 p-8">
      <figcaption className="display-sm">Le détail des métriques</figcaption>
      <p className="mt-2 max-w-2xl text-xs leading-relaxed text-muted-foreground">
        Run avec outils de navigation du 12 octobre 2026 sur le corpus complet : 84 rapports,
        12 000 pages indexées ensemble, 135 questions jugées. Entre parenthèses, le nombre de
        réponses concernées.
      </p>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[24rem] text-sm">
          <thead>
            <tr className="text-left text-xs text-muted-foreground">
              <th className="py-2 pr-4 font-medium">Métrique</th>
              <th className="py-2 font-medium">Résultat</th>
            </tr>
          </thead>
          {metricGroups.map((g) => (
            <tbody key={g.title}>
              <tr>
                <th colSpan={2} className="mono-xs uppercase tracking-[0.09em] text-ink-faint pb-1 pt-5 text-left font-normal">
                  {g.title}
                </th>
              </tr>
              {g.rows.map((r) => (
                <tr key={r.metric} className="border-t border-hairline align-top">
                  <td className="py-2 pr-4">
                    <span className="font-medium">{r.metric}</span>
                    {r.hint && (
                      <span className="mt-0.5 block text-[0.7rem] leading-snug text-muted-foreground">
                        {r.hint}
                      </span>
                    )}
                  </td>
                  <td className="whitespace-nowrap py-2 tabular-nums font-medium">{r.full}</td>
                </tr>
              ))}
            </tbody>
          ))}
        </table>
      </div>
    </figure>
  );
}

function Bar({ value, tone, label }: { value: number; tone: "before" | "notools" | "after"; label: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex h-5 items-center gap-2">
          <span
            className={cn(
              "h-2.5 rounded-r-[4px] transition-[width] duration-700",
              tone === "before" && "bg-chart-before",
              tone === "notools" && "bg-chart-notools",
              tone === "after" && "bg-chart-after",
            )}
            style={{ width: `${value}%` }}
          />
          <span className="mono-xs shrink-0 whitespace-nowrap tabular-nums text-ink-muted">{value.toLocaleString("fr-FR")} %</span>
        </div>
      </TooltipTrigger>
      <TooltipContent>
        {label} · {value.toLocaleString("fr-FR")} %
      </TooltipContent>
    </Tooltip>
  );
}

function Delta({ row }: { row: Row }) {
  const d = row.after - row.noTools;
  const good = row.lowerIsBetter ? d < 0 : d > 0;
  return (
    <span className={cn("tabular-nums", d === 0 ? "text-muted-foreground" : good ? "text-brand-deep" : "text-destructive")}>
      {d === 0 ? "=" : `${d > 0 ? "+" : "−"}${Math.abs(d).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} pts`}
    </span>
  );
}

function BenchmarkChart() {
  const [table, setTable] = useState(false);
  return (
    <figure className="card-paper border-hairline p-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 max-w-2xl">
          <figcaption className="display-sm">
            Du RAG naïf au système agentique
          </figcaption>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
            « Avec outils de navigation » : 84 rapports, 135 questions. « Sans » : mesuré
            sur le pilote de 20 rapports, 65 questions ; à questions identiques,
            les outils font gagner 29 points (53,8 % → 83,1 %).
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto shrink-0 -mt-1"
          onClick={() => setTable((t) => !t)}
          aria-pressed={table}
        >
          <Table2 /> {table ? "Graphique" : "Tableau"}
        </Button>
      </div>

      {table ? (
        <table className="mt-4 w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted-foreground">
              <th className="py-2 font-medium">Métrique</th>
              <th className="py-2 font-medium">RAG naïf</th>
              <th className="py-2 font-medium">Sans outils de navigation</th>
              <th className="py-2 font-medium">Avec outils de navigation</th>
              <th className="py-2 font-medium">Δ outils</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.metric} className="border-t border-hairline">
                <td className="py-2 font-medium">{r.metric}</td>
                <td className="py-2 tabular-nums">
                  {r.before.toLocaleString("fr-FR")} %
                </td>
                <td className="py-2 tabular-nums">
                  {r.noTools.toLocaleString("fr-FR")} %
                </td>
                <td className="py-2 tabular-nums">
                  {r.after.toLocaleString("fr-FR")} %
                </td>
                <td className="py-2">
                  <Delta row={r} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <>
          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1">
            <span className="flex items-center gap-1.5 text-xs text-ink-muted">
              <span className="size-2.5 rounded-sm bg-chart-before" /> RAG naïf
            </span>
            <span className="flex items-center gap-1.5 text-xs text-ink-muted">
              <span className="size-2.5 rounded-sm bg-chart-notools" /> Ce RAG sans outils de navigation
            </span>
            <span className="flex items-center gap-1.5 text-xs text-ink-muted">
              <span className="size-2.5 rounded-sm bg-chart-after" /> Ce RAG avec outils de navigation
            </span>
          </div>
          <div className="mt-5 space-y-5">
            {rows.map((r) => (
              <div
                key={r.metric}
                className="grid gap-1 sm:grid-cols-[11rem_1fr]"
              >
                <div>
                  {/* nowrap : « Fausses ou refusées » passait à la ligne et désalignait
                      les deux libellés. La colonne est commune, donc ils restent alignés. */}
                  <span className="whitespace-nowrap text-sm font-medium">
                    {r.metric}
                  </span>
                  <span className="mt-0.5 block text-[0.7rem] leading-snug text-muted-foreground">
                    {r.hint}
                  </span>
                </div>
                <div className="relative space-y-0.5 border-l border-hairline pl-3">
                  <Bar
                    value={r.before}
                    tone="before"
                    label={`${r.metric} · RAG naïf`}
                  />
                  <Bar
                    value={r.noTools}
                    tone="notools"
                    label={`${r.metric} · ce RAG sans outils de navigation`}
                  />
                  <Bar
                    value={r.after}
                    tone="after"
                    label={`${r.metric} · ce RAG avec outils de navigation`}
                  />
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </figure>
  );
}

export function Results() {
  return (
    <Section
      id="resultats"
      index="03"
      eyebrow="L'évaluation"
      title={
        <>
          Évalué à 88,1 % de réponses correctes sur le benchmark{" "}
          <span className="accent-italic">FinanceBench</span> : 84 rapports
          indexés ensemble, 135 questions.
        </>
      }
      intro="FinanceBench (Patronus AI) est un benchmark de questions financières sur des filings SEC denses en tableaux, où chaque chiffre apparaît des dizaines de fois. L'évaluation de mon RAG agentique porte sur les 84 rapports des questions open source (64 10-K, 8 10-Q, 6 résultats trimestriels, 6 8-K), soit 12 000 pages indexées ensemble dans un seul index : 139 questions, dont 135 jugées (4 n'ont pas abouti, bloquées par le quota de tokens du fournisseur). Le système doit d'abord trouver le bon rapport parmi les 84."
    >
      {/* trois niveaux */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {levels.map((l, i) => (
          <div
            key={l.label}
            className={cn(
              "flex h-full flex-col rounded-xl border p-8",
              l.tone === "muted" && "border-hairline bg-chart-after/5",
              l.tone === "plain" && "border-hairline bg-paper-2",
              l.tone === "brand" && "bg-chart-after/20 shadow-xl",
                          )}
          >
            {/* Le numéro reste calé en haut à droite, même quand le libellé passe sur plusieurs lignes. */}
            <div className="flex items-start justify-between gap-3">
              <span className="eyebrow min-h-[3lh] min-w-0 text-brand">{l.label}</span>
              <span className="mono-xs shrink-0 leading-none text-brand">0{i + 1}</span>
            </div>
            <div className="font-display mt-4 text-5xl font-normal tracking-tight whitespace-nowrap">
              {l.correct}
            </div>
            <div className="mt-1 text-sm font-medium">réponses correctes</div>
            <div className="meta mt-1">{l.wrong}</div>
            <p className="mt-4 border-t border-hairline pt-3 text-xs leading-relaxed text-ink-muted">
              {l.setup}
            </p>
          </div>
        ))}
      </div>
      {/* RAG naïf vs système agentique */}
      <div className="mt-14">
        <BenchmarkChart />
      </div>

      {/* Ce que les chiffres autorisent à dire — et pas plus. Hors de la carte, exprès. */}
      <figure className="pt-18 grid max-w-4xl gap-x-6 sm:grid-cols-[3.5rem_1fr]">
        <span
          aria-hidden
          className="display-xl -mt-3 hidden select-none leading-none text-brand sm:block"
        >
          &ldquo;
        </span>
        <div>
          <span className="eyebrow">Ce que les chiffres disent</span>
          <blockquote className="display-md mt-3 text-ink">
            Sur les 84 rapports de FinanceBench, 12 000 pages indexées
            ensemble, le système
            répond correctement à{" "}
            <span className="accent-italic">119 des 135 questions</span>{" "}
            jugées, avec 15 réponses fausses et 1 refus ; 92,3 % sur le pilote
            de 20 rapports. Le RAG naïf plafonne{" "}
            <span className="accent-italic">
              à ~19 % sur le benchmark complet
            </span>
            . Sans outils de navigation, sur le pilote, le même système n&apos;en répond que
            35 sur 65 : les outils font gagner 29 points sur les mêmes questions.
          </blockquote>
        </div>
      </figure>

      <MetricsTable />

      <div className="mt-16">
        <h3 className="display-md max-w-3xl">Ce qui a été fait</h3>
        <ol className="mt-6 space-y-1">
          {levers.map((l, i) => {
            // Du plus gros gain au plus faible : un or déjà léger au premier rang, qui
            // s'estompe jusqu'au papier au dernier. Le premier rang se marque au filet, pas
            // à la saturation — la teinte reste discrète sur toute la série.
            const strength = 0.2 - (i / (levers.length - 1)) * 0.185;
            const strong = i === 0;
            return (
              <li
                key={l.title}
                data-strong={strong || undefined}
                className="lever-row grid gap-1 rounded-sm px-4 py-4 sm:grid-cols-[2rem_16rem_1fr] sm:gap-4"
                style={
                  {
                    "--lever-strength": `${Math.round(strength * 100)}%`,
                  } as CSSProperties
                }
              >
                <span className="lever-index mono-xs pt-1">0{i + 1}</span>
                <span className="text-sm font-medium">{l.title}</span>
                <span className="lever-text text-sm leading-relaxed">
                  {l.text}
                </span>
              </li>
            );
          })}
        </ol>
      </div>
    </Section>
  );
}
