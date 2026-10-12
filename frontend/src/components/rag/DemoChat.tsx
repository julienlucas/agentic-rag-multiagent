import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowRight, ArrowUp, Clock, RotateCcw, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { api, documentUrl, type Citation } from "@/api";
import { renderMarkdown } from "@/lib/markdown";
import { parseVerificationReport } from "@/lib/verification";
import { useElapsed } from "@/hooks/useTimer";
import {
  AnswerBlock,
  AnswerFeedback,
  CitedSources,
  CiteMark,
  CollapsibleAnswer,
  PipelineProgress,
  QuestionBubble,
  usePipelineStages,
} from "./answer";
import { CorpusPanel } from "./CorpusPanel";
import { DocumentViewer } from "./DocumentViewer";
import { exampleDocs, exampleOutput, type ExampleDoc } from "./examples";
import type { DocState, Turn } from "./types";

const DEFAULT_EXAMPLE = exampleDocs[0];
const EXAMPLE_SIGNALS = parseVerificationReport(exampleOutput.report);

function docFromExample(ex: ExampleDoc): DocState {
  return {
    id: ex.id,
    title: ex.title,
    fileName: ex.fileName,
    kind: ex.kind,
    pages: ex.pages,
    type: ex.type,
    description: ex.description,
    source: "example",
    status: "loading",
  };
}

/**
 * Démo publique, sans compte : deux rapports d'exemple déjà indexés, questions illimitées sur
 * eux. Déposer ses propres documents demande un compte (20 documents offerts).
 */
export function DemoChat({ children }: { children?: ReactNode }) {
  const [sessionId] = useState(() => `session_${Date.now().toString(36)}`);
  const [doc, setDoc] = useState<DocState | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const { stage, start, stop } = usePipelineStages();
  const elapsed = useElapsed(pending);
  const viewport = useRef<HTMLDivElement>(null);
  const loadToken = useRef(0);
  const [opened, setOpened] = useState<Citation | null>(null);

  useEffect(() => {
    if (turns.length === 0 && !pending) return;
    const el = viewport.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [turns, pending, stage]);

  /* ---------- chargement d'un exemple ---------- */

  const indexDoc = useCallback(
    async (next: DocState) => {
      const token = ++loadToken.current;
      setDoc({ ...next, status: "loading", chunks: undefined, error: undefined });
      setTurns([]);
      const started = Date.now();
      try {
        const res = await api.loadFile(next.fileName, sessionId);
        if (token !== loadToken.current) return;
        setDoc((d) =>
          d && d.id === next.id
            ? {
                ...d,
                status: "ready",
                chunks: res.chunks_count,
                loadSeconds: Math.max(1, Math.round((Date.now() - started) / 1000)),
              }
            : d,
        );
      } catch (err) {
        if (token !== loadToken.current) return;
        const message = err instanceof Error ? err.message : "Erreur de connexion au backend";
        setDoc((d) => (d && d.id === next.id ? { ...d, status: "error", error: message } : d));
        toast.error("Indexation impossible", { description: message });
      }
    },
    [sessionId],
  );

  useEffect(() => {
    indexDoc(docFromExample(DEFAULT_EXAMPLE));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectExample = (id: string) => {
    const ex = exampleDocs.find((e) => e.id === id);
    if (ex && ex.id !== doc?.id) indexDoc(docFromExample(ex));
  };

  const retry = () => {
    if (doc) indexDoc(doc);
  };

  /* ---------- question ---------- */

  const ready = doc?.status === "ready";
  const busy = pending || doc?.status === "loading";

  async function ask(question: string) {
    const q = question.trim();
    if (!q || !ready || pending) return;

    setDraft("");
    setPending(true);
    start();
    setTurns((t) => [...t, { id: `u-${Date.now()}`, role: "user", text: q }]);

    const started = Date.now();
    try {
      const res = await api.processQuestion(q, sessionId);
      setTurns((t) => [
        ...t,
        {
          id: `a-${Date.now()}`,
          role: "assistant",
          answer: res.draft_answer,
          signals: parseVerificationReport(res.verification_report),
          elapsed: Math.round((Date.now() - started) / 1000),
          citations: res.citations ?? [],
          feedbackToken: res.feedback_token,
        },
      ]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erreur de connexion au backend";
      setTurns((t) => [
        ...t,
        {
          id: `a-${Date.now()}`,
          role: "assistant",
          answer: message,
          signals: parseVerificationReport(`Erreur: ${message}`),
          elapsed: Math.round((Date.now() - started) / 1000),
          citations: [],
          failed: true,
        },
      ]);
      toast.error("Le pipeline a échoué", { description: message });
    } finally {
      stop();
      setPending(false);
    }
  }

  const reset = () => {
    stop();
    setTurns([]);
    setPending(false);
    setDraft("");
  };

  const openCitation = (c: Citation) => {
    if (c.pdf_url || c.file_hash) setOpened(c);
    else toast.info("Ce passage ne peut pas être rouvert");
  };

  const activeExample = doc?.source === "example" ? exampleDocs.find((e) => e.id === doc.id) : undefined;
  const suggestions = activeExample?.questions ?? [];
  const showExample = turns.length === 0 && !pending && doc?.id === exampleOutput.docId;

  return (
    <div>
      {children}

      {/* Conversation à gauche ; documents (exemples + invitation à s'inscrire) à droite, au-dessus sur mobile. */}
      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_17rem]">
        <div className="lg:order-last lg:flex lg:flex-col">
          <CorpusPanel active={doc} onSelectExample={selectExample} onRetry={retry} busy={busy} />
        </div>

        <div className="card-paper min-w-0 overflow-hidden border-brand bg-paper">
          {/* hauteur figée à celle du chargement (exemple affiché) : la conversation défile dedans */}
          <div className="flex h-[53rem] flex-col lg:h-[44.3rem]">
            <ScrollArea className="min-h-0 flex-1" viewportRef={viewport} data-lenis-prevent>
              <div className="space-y-5 p-5">
                {showExample ? (
                  <div className="rise-in space-y-5">
                    {doc?.status === "loading" ? <span className="meta">indexation en cours…</span> : null}
                    <QuestionBubble>{exampleOutput.question}</QuestionBubble>
                    <div className="max-w-[85%]">
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <span className="meta">
                          confiance reranker{" "}
                          {EXAMPLE_SIGNALS.rerankScore != null
                            ? `${Math.round(EXAMPLE_SIGNALS.rerankScore * 100)} %`
                            : null}
                        </span>
                        <span className="meta inline-flex items-center gap-1">
                          <Clock className="size-3" /> {exampleOutput.elapsed}s
                        </span>
                      </div>
                      <div className="flex gap-2.5 rounded-2xl bg-bubble-r px-4 py-3.5">
                        <div className="min-w-0 flex-1">
                          <CollapsibleAnswer>
                            <div className="prose-rag">
                              {renderMarkdown(exampleOutput.answer, (n) => (
                                <CiteMark
                                  n={n}
                                  citation={exampleOutput.citations.find((c) => c.n === n)}
                                  onOpen={openCitation}
                                />
                              ))}
                            </div>
                          </CollapsibleAnswer>
                          <CitedSources
                            answer={exampleOutput.answer}
                            citations={exampleOutput.citations}
                            onOpen={openCitation}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                ) : null}

                {turns.length === 0 && !pending && !showExample ? (
                  <div className="rise-in">
                    <h3 className="display-sm">
                      {doc ? `Interrogez « ${doc.title} ».` : "Chargez un document pour commencer."}
                    </h3>
                    <p className="copy mt-2 text-sm">
                      Le pipeline cible le document, cherche en lexical et en vectoriel, fusionne, reranke,
                      vérifie la pertinence des passages, corrige la recherche si besoin — puis répond
                      uniquement à partir des preuves retenues.
                    </p>
                    {doc?.status === "loading" ? (
                      <p className="meta mt-4">
                        Chargement de l'exemple… la première question sera possible dans quelques secondes.
                      </p>
                    ) : null}
                    {suggestions.length ? (
                      <div className="mt-5 grid gap-2">
                        {suggestions.map((s) => (
                          <button
                            key={s.text}
                            type="button"
                            disabled={!ready}
                            onClick={() => ask(s.text)}
                            className="group flex items-start gap-3 rounded-md border border-hairline bg-paper px-3.5 py-3 text-left text-sm transition-colors hover:border-brand hover:bg-brand-surface disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            <Sparkles className="mt-0.5 size-3.5 shrink-0 text-brand-deep" />
                            <span className="min-w-0 flex-1">
                              <span className="block leading-snug">{s.text}</span>
                              <span className="meta mt-1 block">{s.hint}</span>
                            </span>
                            <ArrowUp className="mt-0.5 size-3.5 shrink-0 rotate-45 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}

                {turns.map((turn) =>
                  turn.role === "user" ? (
                    <QuestionBubble key={turn.id}>{turn.text}</QuestionBubble>
                  ) : (
                    <AnswerBlock
                      key={turn.id}
                      answer={turn.answer}
                      citations={turn.citations}
                      signals={turn.signals}
                      elapsed={turn.elapsed}
                      failed={turn.failed}
                      onOpen={openCitation}
                      footer={
                        !turn.failed && turn.feedbackToken ? (
                          <AnswerFeedback
                            send={(score, comment) => api.sendFeedback(turn.feedbackToken!, score, sessionId, comment)}
                          />
                        ) : null
                      }
                    />
                  ),
                )}

                {pending ? <PipelineProgress stage={stage} elapsed={elapsed} /> : null}
              </div>
            </ScrollArea>

            {/* saisie */}
            <div className="border-t border-hairline p-3 px-5">
              <div className="flex items-end gap-2 rounded-sm border border-hairline-strong bg-paper p-2 transition-colors focus-within:border-brand">
                <textarea
                  rows={1}
                  value={draft}
                  aria-label="Votre question"
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      ask(draft);
                    }
                  }}
                  disabled={!ready || pending}
                  placeholder={
                    ready
                      ? "Posez une question sur le document…"
                      : doc?.status === "loading"
                        ? "Chargement en cours…"
                        : "Choisissez un exemple pour poser une question"
                  }
                  className="max-h-32 min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
                />
                <Button
                  variant="brand"
                  onClick={() => ask(draft)}
                  disabled={!draft.trim() || !ready || pending}
                  className="h-9 shrink-0 px-3.5 disabled:opacity-100"
                >
                  Envoyer
                  <ArrowRight />
                </Button>
              </div>
              {suggestions.length || turns.length ? (
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {suggestions.length ? <span className="meta mr-1">questions préparées</span> : null}
                  {turns.length ? (
                    <Button variant="pill" size="pill" onClick={reset} disabled={pending} className="gap-1 [&_svg]:size-3">
                      <RotateCcw /> Réinitialiser
                    </Button>
                  ) : null}
                  {suggestions.map((s) => (
                    <Button
                      key={s.text}
                      variant="pill"
                      size="pill"
                      disabled={!ready || pending}
                      onClick={() => ask(s.text)}
                      title={s.text}
                    >
                      <span className="truncate">{s.text.slice(0, 48)}…</span>
                    </Button>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      {opened ? (
        <DocumentViewer
          key={`${opened.source}-${opened.n}-${opened.page}`}
          citation={opened}
          url={opened.pdf_url ? documentUrl(opened.pdf_url, sessionId) : null}
          pageText={
            opened.file_hash
              ? (page) => api.pageText(opened.file_hash!, page, sessionId).then((r) => r.text)
              : undefined
          }
          onClose={() => setOpened(null)}
        />
      ) : null}
    </div>
  );
}
