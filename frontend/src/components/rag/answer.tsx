/*
 * Briques d'une conversation avec le RAG, partagées par la démo publique (DemoChat) et le chat
 * de l'espace connecté (ChatPage) : bulle de question, réponse repliable avec citations [n],
 * passages cités, vote 👍 / 👎, progression estimée du pipeline.
 */
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { ChevronDown, Clock, ShieldAlert, Sparkles, ThumbsDown, ThumbsUp } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { Citation } from "@/api";
import { renderMarkdown } from "@/lib/markdown";
import type { VerificationSignals } from "@/lib/verification";
import { pipelineSteps } from "./pipeline";

const MAX_ANSWER_H = 130;

/** Réponse repliée à 130 px, dépliable par « Voir la suite ». */
export function CollapsibleAnswer({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [overflows, setOverflows] = useState(false);
  const [fullHeight, setFullHeight] = useState(0);
  const inner = useRef<HTMLDivElement>(null);

  /* mesure avant peinture : sinon le bloc s'affiche déplié puis se referme */
  useLayoutEffect(() => {
    const el = inner.current;
    if (!el) return;
    const check = () => {
      setFullHeight(el.scrollHeight);
      setOverflows(el.scrollHeight > MAX_ANSWER_H + 8);
    };
    check();
    const ro = new ResizeObserver(check);
    ro.observe(el);
    return () => ro.disconnect();
  }, [children]);

  const collapsed = overflows && !open;

  return (
    <div>
      <div
        className="relative overflow-hidden transition-[max-height] duration-300"
        style={{ maxHeight: collapsed ? MAX_ANSWER_H : fullHeight }}
      >
        <div ref={inner} className="!text-xs !leading-relaxed !text-ink-muted">
          {children}
        </div>
        {overflows && !open ? (
          <span
            aria-hidden
            className="pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-bubble-r to-transparent"
          />
        ) : null}
      </div>
      {overflows ? (
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="mono-xs mt-2 inline-flex items-center gap-1 text-brand-deep transition-colors hover:text-brand-strong cursor-pointer"
        >
          {open ? "Réduire" : "Voir la suite"}
          <ChevronDown className={cn("size-3 transition-transform", open && "rotate-180")} />
        </button>
      ) : null}
    </div>
  );
}

/** Ouvre le document d'une citation à la page citée ; null si elle ne peut pas l'être. */
export type OpenCitation = ((c: Citation) => void) | null;

/** Marqueur de citation [n] : renvoie au passage transmis au modèle ; un clic ouvre le document. */
export function CiteMark({ n, citation, onOpen }: { n: number; citation?: Citation; onOpen?: OpenCitation }) {
  const openable = Boolean(citation && onOpen);
  const mark = (
    <sup
      role={openable ? "button" : undefined}
      tabIndex={openable ? 0 : undefined}
      onClick={openable ? () => onOpen!(citation!) : undefined}
      onKeyDown={openable ? (e) => e.key === "Enter" && onOpen!(citation!) : undefined}
      className={cn(
        "mono-xs ml-0.5 rounded bg-brand-surface-strong px-1 py-px text-[0.6rem] text-brand-deep",
        openable ? "cursor-pointer hover:bg-brand hover:text-on-brand" : "cursor-help",
      )}
    >
      {n}
    </sup>
  );
  if (!citation) return mark;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{mark}</TooltipTrigger>
      <TooltipContent className="max-w-sm bg-brand text-on-brand">
        <span className="mono-xs block text-on-brand/75">{citation.locator}</span>
        <span className="mt-1 block text-xs leading-relaxed">{citation.excerpt}</span>
        {openable ? <span className="mono-xs mt-1.5 block text-on-brand/75">cliquer pour ouvrir le passage</span> : null}
      </TooltipContent>
    </Tooltip>
  );
}

/** Liste des passages réellement cités dans la réponse ; un clic ouvre le document au passage. */
export function CitedSources({
  answer,
  citations,
  onOpen,
}: {
  answer: string;
  citations: Citation[];
  onOpen?: OpenCitation;
}) {
  const used = Array.from(new Set([...answer.matchAll(/\[(\d+)\]/g)].map((m) => Number(m[1]))))
    .sort((a, b) => a - b)
    .map((n) => citations.find((c) => c.n === n))
    .filter((c): c is Citation => Boolean(c));
  if (!used.length) return null;
  return (
    <div className="mt-3 border-t border-hairline pt-3">
      <span className="eyebrow">Passages cités</span>
      <ul className="mt-2 space-y-1.5">
        {used.map((c) => {
          const body = (
            <>
              <span className="mono-xs mt-px inline-grid size-4 shrink-0 place-items-center rounded bg-brand-surface-strong text-[0.6rem] leading-none text-brand-deep">
                {c.n}
              </span>
              <span className="min-w-0 flex-1">
                <span className="font-medium text-ink-muted">{c.locator}</span> — {c.excerpt}
              </span>
            </>
          );
          return (
            <li key={c.n} className="text-[0.7rem] leading-relaxed text-muted-foreground">
              {onOpen ? (
                <button
                  type="button"
                  onClick={() => onOpen(c)}
                  title="Ouvrir le document à ce passage"
                  className="flex w-full cursor-pointer gap-2 rounded-sm text-left transition-colors hover:bg-brand-surface hover:text-ink"
                >
                  {body}
                </button>
              ) : (
                <div className="flex gap-2">{body}</div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/**
 * Vote 👍 / 👎 sous une réponse. Le 👎 ouvre un commentaire facultatif avant l'envoi.
 * Un seul vote par réponse : il devient un exemple du jeu de non-régression (evaluation/feedback/).
 */
export function AnswerFeedback({ send }: { send: (score: 0 | 1, comment?: string) => Promise<unknown> }) {
  const [state, setState] = useState<"idle" | "comment" | "sending" | "done">("idle");
  const [vote, setVote] = useState<0 | 1 | null>(null);
  const [comment, setComment] = useState("");

  async function submit(score: 0 | 1, text?: string) {
    setVote(score);
    setState("sending");
    try {
      await send(score, text?.trim() || undefined);
      setState("done");
    } catch (err) {
      setState(score === 0 ? "comment" : "idle");
      if (score === 1) setVote(null);
      toast.error("Vote non enregistré", {
        description: err instanceof Error ? err.message : "Erreur de connexion au backend",
      });
    }
  }

  const voteButton = (score: 0 | 1) => {
    const Icon = score === 1 ? ThumbsUp : ThumbsDown;
    const label = score === 1 ? "Réponse satisfaisante" : "Réponse pas satisfaisante";
    return (
      <button
        type="button"
        aria-label={label}
        title={label}
        aria-pressed={vote === score}
        disabled={state === "sending" || state === "done"}
        onClick={() => (score === 1 ? submit(1) : (setVote(0), setState("comment")))}
        className={cn(
          "inline-grid size-7 cursor-pointer place-items-center rounded-sm border transition-colors",
          vote === score
            ? "border-brand bg-brand-surface text-brand-deep"
            : "border-transparent text-muted-foreground hover:border-hairline hover:text-brand-deep",
          state === "done" && vote !== score && "hidden",
        )}
      >
        <Icon className="size-3.5" />
      </button>
    );
  };

  return (
    <div className="mt-1.5">
      <div className="flex items-center gap-1">
        {voteButton(1)}
        {voteButton(0)}
        {state === "done" ? (
          <span className="meta ml-1">merci pour votre retour</span>
        ) : (
          <span className="meta ml-1">Notez les réponses, surtout si elles sont insatisfaisantes</span>
        )}
      </div>
      {state === "comment" || (state === "sending" && vote === 0) ? (
        <div className="rise-in mt-2 rounded-sm border border-hairline-strong bg-paper p-2">
          <textarea
            rows={2}
            autoFocus
            value={comment}
            maxLength={2000}
            aria-label="Commentaire sur la réponse"
            onChange={(e) => setComment(e.target.value)}
            placeholder="Qu'est-ce qui ne va pas ? (facultatif : mauvais chiffre, mauvais document, réponse incomplète…)"
            className="w-full resize-none bg-transparent px-1 text-xs outline-none placeholder:text-muted-foreground"
          />
          <div className="mt-1 flex justify-end gap-1.5">
            <Button
              variant="pill"
              size="pill"
              disabled={state === "sending"}
              onClick={() => {
                setVote(null);
                setComment("");
                setState("idle");
              }}
            >
              Annuler
            </Button>
            <Button variant="pill" size="pill" disabled={state === "sending"} onClick={() => submit(0, comment)}>
              Envoyer
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

/** Bulle de question, alignée à droite. */
export function QuestionBubble({ children }: { children: ReactNode }) {
  return (
    <div className="flex justify-end">
      <p className="rise-in flex max-w-[85%] gap-2.5 rounded-2xl rounded-br-sm bg-bubble-q px-4 py-2.5 text-sm leading-relaxed text-on-brand">
        <span className="min-w-0 flex-1 whitespace-pre-wrap">{children}</span>
      </p>
    </div>
  );
}

/**
 * Réponse du RAG : méta (confiance, durée, coût), réponse markdown avec citations,
 * passages cités, mention de la recherche à outils, puis `footer` (vote, coût…).
 */
export function AnswerBlock({
  answer,
  citations,
  signals,
  elapsed,
  failed,
  meta,
  footer,
  onOpen,
}: {
  answer: string;
  citations: Citation[];
  signals?: VerificationSignals;
  elapsed?: number;
  failed?: boolean;
  meta?: ReactNode;
  footer?: ReactNode;
  onOpen?: OpenCitation;
}) {
  return (
    <div className="rise-in max-w-[95%]">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        {signals?.rerankScore != null ? (
          <span className="meta">confiance reranker {Math.round(signals.rerankScore * 100)}&nbsp;%</span>
        ) : null}
        {elapsed != null ? (
          <span className="meta inline-flex items-center gap-1">
            <Clock className="size-3" /> {elapsed}s
          </span>
        ) : null}
        {meta}
      </div>
      <div
        className={cn(
          "flex gap-2.5 rounded-2xl border px-4 py-3.5",
          failed ? "border-destructive/40 bg-destructive/5" : "border-transparent bg-bubble-r",
        )}
      >
        <div className="min-w-0 flex-1">
          {failed ? (
            <div className="flex gap-2 text-sm text-destructive">
              <ShieldAlert className="mt-0.5 size-4 shrink-0" />
              <div className="min-w-0">{answer}</div>
            </div>
          ) : (
            <CollapsibleAnswer>
              <div className="prose-rag">
                {renderMarkdown(answer, (n) => (
                  <CiteMark n={n} citation={citations.find((c) => c.n === n)} onOpen={onOpen} />
                ))}
              </div>
            </CollapsibleAnswer>
          )}
          {!failed ? <CitedSources answer={answer} citations={citations} onOpen={onOpen} /> : null}
          {!failed && signals && signals.correctiveRounds > 0 ? (
            <p className="mt-3 flex gap-2 border-t border-hairline pt-3 text-xs text-muted-foreground">
              <Sparkles className="mt-0.5 size-3.5 shrink-0 text-brand-deep" />
              Le modèle a jugé le contexte insuffisant et a cherché lui-même (search, grep, read_page,
              navigate…) avant de répondre — le détail est dans le rapport.
            </p>
          ) : null}
        </div>
      </div>
      {footer}
    </div>
  );
}

/** Progression estimée du pipeline (le backend ne streame pas). */
export function PipelineProgress({ stage, elapsed }: { stage: number; elapsed: number }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="rise-in space-y-2 rounded-2xl border border-dashed border-brand/50 bg-brand-surface/40 px-4 py-3.5"
    >
      {pipelineSteps
        .filter((s) => !s.conditional)
        .map((s) => {
          const i = pipelineSteps.indexOf(s);
          const done = stage > i;
          const running = stage === i;
          return (
            <div
              key={s.key}
              className={cn("flex items-center gap-2.5 text-xs transition-opacity", !done && !running && "opacity-40")}
            >
              {done ? (
                <span className="size-3.5 shrink-0 rounded-full bg-success/80" />
              ) : (
                <span
                  className={cn("size-3.5 shrink-0 rounded-full border border-brand", running && "signal-dot bg-brand")}
                />
              )}
              <span className={cn("font-medium", done && "text-ink-muted")}>{s.label}</span>
              {running ? <span className="meta">en cours…</span> : null}
            </div>
          );
        })}
      <p className="meta pt-1">{elapsed}s · 3 à 5 appels LLM en série, comptez 10 à 40 s</p>
    </div>
  );
}

/**
 * Anime les étapes du pipeline pendant une question. `start()` lance la minuterie,
 * `stop()` la coupe ; `stage` est l'étape affichée.
 */
export function usePipelineStages() {
  const [stage, setStage] = useState(0);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  useEffect(() => () => timers.current.forEach(clearTimeout), []);
  const stop = () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setStage(pipelineSteps.length);
  };
  const start = () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setStage(0);
    let acc = 0;
    pipelineSteps.forEach((s, i) => {
      if (s.ms > 0 && i + 1 < pipelineSteps.length) {
        acc += s.ms;
        const nextIndex = pipelineSteps[i + 1].conditional ? i + 2 : i + 1;
        timers.current.push(setTimeout(() => setStage(nextIndex), acc));
      }
    });
  };
  return { stage, start, stop };
}
