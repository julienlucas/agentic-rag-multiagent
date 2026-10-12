import { Check, X } from "lucide-react";
import { Section } from "@/components/site/primitives";
import { GITHUB_REPO } from "@/components/site/links";
import { cn } from "@/lib/utils";

/*
 * 01 · Évaluation. Chiffres des expériences LangSmith du 12 octobre 2026 (README, « Résultats ») :
 * corpus complet de 84 rapports, puis l'ablation sans / avec outils, à retrieval identique.
 */

const HEADLINE = [
  { value: "88,1 %", label: "de réponses correctes", detail: "119 sur 135 questions jugées" },
  { value: "84", label: "rapports SEC", detail: "10-K, 10-Q, 8-K, résultats trimestriels" },
  { value: "12 000", label: "pages indexées ensemble", detail: "un seul index : trouver le bon rapport fait partie du test" },
  { value: "135", label: "questions d'analystes", detail: "ratios, tendances, faits, oui / non" },
];

type Run = {
  name: string;
  kind: string;
  correct: number;
  wrong: number;
  refused: number;
  seconds: string;
  tokens: string;
  how: string;
  points: [boolean, string][];
};

const TOTAL = 65;

const RUNS: [Run, Run] = [
  {
    name: "RAG classique",
    kind: "sans outils de navigation",
    correct: 35,
    wrong: 15,
    refused: 15,
    seconds: "7,0 s",
    tokens: "≈ 3 000",
    how: "Reçoit les 10 meilleurs passages et répond en une seule passe. Si la preuve n'y est pas, il ne peut pas aller la chercher.",
    points: [
      [false, "Un tableau coupé entre deux passages reste illisible"],
      [false, "Une note en page 87 n'est jamais lue si la recherche l'a manquée"],
      [false, "Faute de preuve, il refuse ou devine"],
    ],
  },
  {
    name: "Agentic Search",
    kind: "avec outils de navigation",
    correct: 54,
    wrong: 11,
    refused: 0,
    seconds: "11,0 s",
    tokens: "≈ 18 000",
    how: "Part des mêmes passages, puis cherche ce qui manque : il relance une recherche, ouvre le plan du rapport, lit la page entière.",
    points: [
      [true, "Lit le tableau complet sur la page, en-têtes compris"],
      [true, "grep confirme qu'un terme figure — ou non — dans tout le document"],
      [true, "Chaque chiffre est cité, la page s'ouvre au passage"],
    ],
  },
];

const TOOLS = ["search", "grep", "read_page", "open_doc", "navigate"];

function pct(n: number) {
  return `${((n / TOTAL) * 100).toFixed(1).replace(".", ",")} %`;
}

function OutcomeBar({ run, strong }: { run: Run; strong?: boolean }) {
  const parts = [
    { n: run.correct, label: "correctes", cls: strong ? "bg-brand" : "bg-ink-soft" },
    { n: run.wrong, label: "fausses", cls: "bg-hairline-strong" },
    { n: run.refused, label: "refus", cls: "bg-paper-3 [background-image:repeating-linear-gradient(135deg,var(--hairline-strong)_0_1px,transparent_1px_6px)]" },
  ];
  return (
    <div>
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-paper-2" role="img"
        aria-label={`${run.correct} correctes, ${run.wrong} fausses, ${run.refused} refus sur ${TOTAL}`}>
        {parts.filter((p) => p.n).map((p) => (
          <span key={p.label} className={p.cls} style={{ width: `${(p.n / TOTAL) * 100}%` }} />
        ))}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
        {parts.map((p) => (
          <li key={p.label} className="meta inline-flex items-center gap-1.5">
            <span aria-hidden className={cn("inline-block size-2 rounded-full", p.cls)} />
            {p.n} {p.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

function RunCard({ run, strong }: { run: Run; strong?: boolean }) {
  return (
    <article
      className={cn(
        "flex flex-col rounded-[var(--radius-media)] border p-6 sm:p-8",
        strong ? "border-brand bg-paper shadow-[0_24px_60px_-30px_color-mix(in_srgb,var(--orange-500)_55%,transparent)]" : "border-hairline bg-paper-2",
      )}
    >
      <header className="flex items-start justify-between gap-4">
        <div>
          <h3 className="display-sm">{run.name}</h3>
          <p className="meta mt-1">{run.kind}</p>
        </div>
        {strong ? <span className="tag border-brand text-brand-deep">Ce RAG</span> : <span className="tag">Référence</span>}
      </header>

      <p className="mt-8 flex items-baseline gap-3">
        <span className={cn("font-display text-[clamp(3rem,2rem+3vw,4.5rem)] leading-none font-semibold tracking-[-0.04em]",
          strong ? "text-ink" : "text-ink-muted")}>
          {pct(run.correct)}
        </span>
        <span className="text-sm text-ink-muted">de réponses correctes</span>
      </p>
      <div className="mt-6">
        <OutcomeBar run={run} strong={strong} />
      </div>

      <p className="mt-8 text-[0.95rem] leading-relaxed text-ink-muted">{run.how}</p>
      <ul className="mt-5 space-y-2.5">
        {run.points.map(([ok, text]) => (
          <li key={text} className="flex gap-2.5 text-sm text-ink">
            {ok ? (
              <Check className="mt-0.5 size-4 shrink-0 text-brand-deep" aria-label="Oui" />
            ) : (
              <X className="mt-0.5 size-4 shrink-0 text-ink-faint" aria-label="Non" />
            )}
            {text}
          </li>
        ))}
      </ul>

      <dl className="mt-8 grid grid-cols-3 gap-4 border-t border-hairline pt-6">
        {[
          ["Fausses ou refus", `${run.wrong + run.refused}`],
          ["Génération", run.seconds],
          ["Tokens lus", run.tokens],
        ].map(([k, v]) => (
          <div key={k}>
            <dt className="meta">{k}</dt>
            <dd className="mt-1 font-display text-xl tracking-tight text-ink">{v}</dd>
          </div>
        ))}
      </dl>
    </article>
  );
}

export function Evaluation() {
  return (
    <Section
      id="evaluation"
      index="01"
      eyebrow="Évaluation"
      title={
        <>
          Mesuré sur <span className="accent-italic">FinanceBench</span>, pas sur une démo.
        </>
      }
      intro={
        <p>
          FinanceBench (Patronus AI) réunit des questions d'analystes financiers sur des rapports publics
          d'entreprises américaines. Nous avons indexé les 84 rapports du jeu ouvert dans un seul index : le
          système doit d'abord trouver le bon rapport parmi 12 000 pages, puis le bon chiffre. Chaque réponse est
          jugée par un modèle hors de la famille Claude (Qwen3 235B), calibré sur une annotation humaine.
        </p>
      }
    >
      <ul className="grid grid-cols-2 gap-px overflow-hidden rounded-[var(--radius-media)] border border-hairline bg-hairline lg:grid-cols-4">
        {HEADLINE.map((h, i) => (
          <li key={h.label} className={cn("bg-paper p-5 sm:p-6", i === 0 && "bg-brand-surface-strong")}>
            <p className="font-display text-[clamp(2rem,1.5rem+1.8vw,3rem)] leading-none font-semibold tracking-[-0.035em] text-ink">
              {h.value}
            </p>
            <p className="mt-3 text-sm font-medium text-ink">{h.label}</p>
            <p className="meta mt-1.5 leading-snug">{h.detail}</p>
          </li>
        ))}
      </ul>
      <p className="meta mt-4">
        92,3 % sur le pilote de 20 rapports · intervalle de confiance à 95 % : 82 à 93 % · ≈ 0,07 $ par question
      </p>

      <div className="mt-20">
        <h3 className="display-md max-w-3xl">Ce que changent les outils de navigation</h3>
        <p className="copy mt-4">
          Même recherche hybride, mêmes 65 questions, mêmes 20 rapports (3 048 pages), même modèle (Claude Sonnet
          4.6). Une seule différence : le modèle qui répond peut-il, ou non, aller lire le document ?
        </p>

        <div className="mt-10 grid gap-5 lg:grid-cols-2">
          <RunCard run={RUNS[0]} />
          <RunCard run={RUNS[1]} strong />
        </div>

        <div className="mt-5 grid gap-px overflow-hidden rounded-[var(--radius-media)] border border-hairline bg-hairline sm:grid-cols-3">
          {[
            ["+29 points", "de réponses correctes"],
            ["−63 %", "de réponses fausses ou refusées"],
            ["+4 secondes", "par question, le prix de la lecture"],
          ].map(([v, l]) => (
            <div key={v} className="bg-paper px-6 py-5">
              <p className="font-display text-2xl font-semibold tracking-tight text-brand-deep">{v}</p>
              <p className="mt-1 text-sm text-ink-muted">{l}</p>
            </div>
          ))}
        </div>

        <div className="mt-8 flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="meta">Les outils de l'agent</span>
          {TOOLS.map((t) => (
            <code key={t} className="mono-xs rounded-sm border border-hairline bg-paper-2 px-1.5 py-0.5 text-ink">
              {t}
            </code>
          ))}
          <a href={`${GITHUB_REPO}#évaluation-financebench-documents-financiers-difficiles`} target="_blank" rel="noreferrer"
            className="mono-xs ml-auto text-brand-deep hover:underline">
            Protocole et résultats question par question ↗
          </a>
        </div>
        <p className="meta mt-6 max-w-3xl leading-relaxed">
          Pour situer : le RAG naïf de l'article FinanceBench (GPT-4 Turbo, 2023) répondait correctement à environ
          19 % des questions. Expériences LangSmith du 12 octobre 2026 ; 4 questions du corpus complet, bloquées par
          un quota Bedrock, ne sont pas comptées.
        </p>
      </div>
    </Section>
  );
}
