import { useState } from "react";
import { Table2 } from "lucide-react";
import { Section } from "@/components/site/primitives";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/*
 * Chiffres : evaluation/financebench/outputs/financebench_summary.json — run du 2 sept. 2026,
 * 21 questions, 3 rapports 10-K, index combiné, juge LLM au protocole du benchmark.
 * Comptages bruts affichés à côté des pourcentages : on est sur 21 questions.
 * Le niveau « RAG naïf » est le chiffre publié dans le papier FinanceBench (Islam et al., 2023)
 * pour un RAG naïf sur vector store partagé, sur le benchmark complet — il n'a pas été re-mesuré
 * sur ce sous-ensemble.
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
    label: "Ce système",
    setup:
      "OCR Mistral · chunking parent / enfant · hybride BM25 + vecteurs · routage · reranking Cohere · vérificateur de pertinence · génération contrainte aux preuves",
    correct: "71,4 %",
    wrong: "15 bonnes réponses sur 21 · 6 fausses · 0 refus",
    tone: "brand" as const,
  },
  {
    label: "Agentic Search · Mistral",
    setup:
      "Mistral Medium 3.5, boucle agentique + navigation · 150 questions sur les 368 filings du benchmark complet",
    correct: "86 %",
    wrong: "one-shot RAG du même modèle : 26,7 %",
    tone: "ref" as const,
  },
];

type Row = {
  metric: string;
  before: number;
  after: number;
  mistral: number;
  hint: string;
  lowerIsBetter?: boolean;
};

const rows: Row[] = [
  {
    metric: "Correctes",
    before: 19,
    after: 71.4,
    mistral: 86,
    hint: "accuracy · verdict CORRECT du juge LLM · 15 sur 21",
  },
  {
    metric: "Fausses ou refusées",
    before: 81,
    after: 28.6,
    mistral: 14,
    hint: "28,6 % d'hallucinations + 0 % de refus · plus bas = mieux",
    lowerIsBetter: true,
  },
];

const levers = [
  {
    title: "OCR Mistral",
    text: "Les tableaux d'un 10-K survivent à l'extraction, en markdown, avec le numéro de page conservé sur chaque chunk.",
  },
  {
    title: "Chunking parent / enfant",
    text: "Petits chunks (400 car.) pour matcher, parents (1 200 car.) transmis au modèle pour répondre avec le contexte.",
  },
  {
    title: "Recherche hybride + routage",
    text: "BM25 et vecteurs fusionnés par RRF, un routeur qui cible le bon document avant de chercher.",
  },
  {
    title: "Reranking Cohere",
    text: "40 candidats rescorés, 30 conservés : les distracteurs sortent du top. Le plus gros gain du projet.",
  },
  {
    title: "Agent vérificateur de pertinence",
    text: "Les passages sont classés CAN_ANSWER / PARTIAL / NO_MATCH avant génération. La recherche corrective câblée derrière part bien sur NO_MATCH, mais son seuil de reranker n'a jamais rien déclenché sur les questions PARTIAL — celles-là mêmes où le système perd des réponses. Seuil à recalibrer.",
  },
  {
    title: "Génération contrainte",
    text: "Mistral Large ne répond qu'à partir des passages retenus et refuse quand la preuve manque.",
  },
];

function Bar({ value, tone, label }: { value: number; tone: "before" | "after" | "mistral"; label: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex h-5 items-center gap-2">
          <span
            className={cn(
              "h-2.5 rounded-r-[4px] transition-[width] duration-700",
              tone === "before" && "bg-chart-before",
              tone === "after" && "bg-chart-after",
              tone === "mistral" && "bg-chart-ref",
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
  const d = row.after - row.before;
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
    <figure className="card-paper p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 max-w-2xl">
          <figcaption className="display-sm">Du RAG naïf au système agentique</figcaption>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto shrink-0"
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
              <th className="py-2 font-medium">Avant</th>
              <th className="py-2 font-medium">Après</th>
              <th className="py-2 font-medium">Δ</th>
              <th className="py-2 font-medium">Mistral Agentic Search</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.metric} className="border-t border-border">
                <td className="py-2 font-medium">{r.metric}</td>
                <td className="py-2 tabular-nums">{r.before.toLocaleString("fr-FR")} %</td>
                <td className="py-2 tabular-nums">{r.after.toLocaleString("fr-FR")} %</td>
                <td className="py-2">
                  <Delta row={r} />
                </td>
                <td className="py-2 tabular-nums text-ink-muted">
                  {r.mistral.toLocaleString("fr-FR")} %
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <>
          <div className="mt-4 flex items-center gap-4">
            <span className="flex items-center gap-1.5 text-xs text-ink-muted">
              <span className="size-2.5 rounded-sm bg-chart-before" /> Avant
            </span>
            <span className="flex items-center gap-1.5 text-xs text-ink-muted">
              <span className="size-2.5 rounded-sm bg-chart-after" /> Après
            </span>
            <span className="flex items-center gap-1.5 text-xs text-ink-muted">
              <span className="size-2.5 rounded-sm bg-chart-ref" /> Mistral Agentic Search
            </span>
          </div>
          <div className="mt-5 space-y-5">
            {rows.map((r) => (
              <div key={r.metric} className="grid gap-1 sm:grid-cols-[11rem_1fr]">
                <div>
                  {/* nowrap : « Fausses ou refusées » passait à la ligne et désalignait
                      les deux libellés. La colonne est commune, donc ils restent alignés. */}
                  <span className="whitespace-nowrap text-sm font-medium">{r.metric}</span>
                  <span className="mt-0.5 block text-[0.7rem] leading-snug text-muted-foreground">{r.hint}</span>
                </div>
                <div className="relative space-y-0.5 border-l border-border pl-3">
                  <Bar value={r.before} tone="before" label={`${r.metric} · avant`} />
                  <Bar value={r.after} tone="after" label={`${r.metric} · après`} />
                  <Bar value={r.mistral} tone="mistral" label={`${r.metric} · Mistral Agentic Search`} />
                </div>
              </div>
            ))}
          </div>
        </>
      )}
      <p className="mt-5 border-t border-border pt-3 text-xs leading-relaxed text-muted-foreground">
        Repère externe : Mistral publie 86 % de réponses correctes avec Agentic Search sur FinanceBench
        (Mistral Medium 3.5, 150 questions sur les 368 filings), contre 26,7 % pour le même modèle en RAG
        one-shot. Trois échantillons différents — benchmark complet pour le papier et pour Mistral,
        21 questions ici — donc un repère, pas un match toutes choses égales.
        <br />
        Le même pipeline sans sa couche multi-agent obtient 17 bonnes réponses sur 21 sur ce run :
        à cette taille d&apos;échantillon, l&apos;apport des agents n&apos;est pas encore démontré, et
        c&apos;est le retrieval qui porte le résultat.
      </p>
    </figure>
  );
}

export function Results() {
  return (
    <Section
      id="resultats"
      index="01"
      eyebrow="L'évaluation"
      title={
        <>
          Évalué à 71 % de réponses correctes sur le benchmark{" "}
          <span className="accent-italic">FinanceBench</span> de 150 à 260
          pages.
        </>
      }
      intro="FinanceBench est le benchmark que Mistral utilise pour évaluer leur outil Agentic Search : des questions financières sur des filings SEC denses en tableaux, où chaque chiffre apparaît des dizaines de fois. Évaluation ici sur 21 questions et 3 rapports (AMD, American Express, Boeing)."
    >
      {/* trois niveaux */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {levels.map((l, i) => (
          <div
            key={l.label}
            className={cn(
              "flex h-full flex-col rounded-xl border p-6",
              l.tone === "muted" && "border-border bg-paper-2",
              l.tone === "brand" && "border-brand bg-paper shadow-card",
              l.tone === "ref" && "border-dashed border-chart-ref/50 bg-paper-2",
            )}
          >
            <div className="flex items-center justify-between">
              <span className="eyebrow">{l.label}</span>
              <span className="mono-xs text-sand-deep">0{i + 1}</span>
            </div>
            <div className="font-display mt-4 text-5xl font-normal tracking-tight">
              {l.correct}
            </div>
            <div className="mt-1 text-sm font-medium">réponses correctes</div>
            <div className="mono-xs mt-1 text-muted-foreground">{l.wrong}</div>
            <p className="mt-4 border-t border-border pt-3 text-xs leading-relaxed text-ink-muted">
              {l.setup}
            </p>
          </div>
        ))}
      </div>
      {/* RAG naïf vs système agentique */}
      <div className="mt-14">
        <BenchmarkChart />
      </div>

      <div className="mt-14">
        <h3 className="display-md max-w-3xl">Ce qui a été fait pour passer du RAG naïf à ce résultat</h3>
        <ol className="mt-6 divide-y divide-border border-t border-border">
          {levers.map((l, i) => (
            <li
              key={l.title}
              className="grid gap-1 py-4 sm:grid-cols-[2rem_16rem_1fr] sm:gap-4"
            >
              <span className="mono-xs pt-1 text-sand-deep">0{i + 1}</span>
              <span className="text-sm font-medium">{l.title}</span>
              <span className="text-sm leading-relaxed text-ink-muted">
                {l.text}
              </span>
            </li>
          ))}
        </ol>
      </div>

      <div className="mt-14">
        <div className="flex flex-col">
          <p className="display-md mt-3">Ce qui limite encore</p>
          <ul className="mt-5 space-y-2">
            {[
              "Dans un tiers des cas, la page de preuve n'atteint jamais le modèle.",
              "Il ne peut pas répondre juste à partir d'une preuve qu'il n'a pas vue.",
              "Les prochains gains sont dans le reranker et le routage, pas dans un modèle plus gros.",
            ].map((point) => (
              <li key={point} className="flex gap-2.5 text-sm leading-relaxed text-ink-muted">
                <span aria-hidden className="mt-2 size-1 shrink-0 rounded-full bg-brand" />
                <span className="min-w-0 flex-1">{point}</span>
              </li>
            ))}
          </ul>
          <p className="mt-4 border-t border-sand pt-3 text-xs leading-relaxed text-muted-foreground">
            21 questions d'évaluation : assez pour repérer les modes d'échec,
            trop peu pour des intervalles de confiance serrés.
          </p>
        </div>
      </div>
    </Section>
  );
}
