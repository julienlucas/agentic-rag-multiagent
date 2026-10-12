import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, Coins, History, Loader2, Plus, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  appApi,
  ApiError,
  documentUrl,
  type AppDocument,
  type Citation,
  type ConversationSummary,
  type Message,
} from "@/api";
import { AnswerBlock, AnswerFeedback, PipelineProgress, QuestionBubble, usePipelineStages } from "@/components/rag/answer";
import { DocumentViewer } from "@/components/rag/DocumentViewer";
import { useElapsed } from "@/hooks/useTimer";
import { errorMessage } from "@/lib/http";
import { credits, usePricing, useSession } from "@/lib/session";
import { parseVerificationReport } from "@/lib/verification";
import { cn } from "@/lib/utils";

/** Document d'une citation : `document_id`, sinon son URL (/api/app/documents/<id>/file), sinon son nom. */
function citedDocument(c: Citation, documents: AppDocument[]): AppDocument | undefined {
  if (c.document_id) {
    const byId = documents.find((d) => d.id === c.document_id);
    if (byId) return byId;
  }
  const fromUrl = c.pdf_url?.match(/\/api\/app\/documents\/([^/]+)\/file/)?.[1];
  if (fromUrl) return documents.find((d) => d.id === fromUrl);
  const stem = (name: string) => name.replace(/\.[^.]+$/, "");
  return documents.find((d) => stem(d.name) === c.source || d.name === c.source);
}

const relativeDate = (iso: string) =>
  new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" }).format(new Date(iso));

function ConversationList({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
}: {
  conversations: ConversationSummary[] | null;
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="p-3">
        <Button variant="outline" size="sm" className="w-full" onClick={onNew}>
          <Plus /> Nouvelle conversation
        </Button>
      </div>
      <span className="eyebrow px-4 pt-2">Historique</span>
      <ScrollArea className="min-h-0 flex-1" data-lenis-prevent>
        <ul className="space-y-0.5 p-2">
          {conversations === null ? (
            <li className="meta px-2 py-2">chargement…</li>
          ) : conversations.length === 0 ? (
            <li className="meta px-2 py-2">aucune conversation</li>
          ) : (
            conversations.map((c) => (
              <li key={c.id} className="group relative">
                <button
                  type="button"
                  onClick={() => onSelect(c.id)}
                  aria-current={c.id === activeId ? "true" : undefined}
                  className={cn(
                    "block w-full cursor-pointer rounded-sm px-3 py-2 pr-9 text-left text-sm transition-colors",
                    c.id === activeId ? "bg-brand-surface text-ink" : "text-ink-muted hover:bg-paper-3 hover:text-ink",
                  )}
                >
                  <span className="block truncate">{c.title || "Sans titre"}</span>
                  <span className="meta">{relativeDate(c.updated_at)}</span>
                </button>
                <button
                  type="button"
                  aria-label={`Supprimer « ${c.title} »`}
                  onClick={() => onDelete(c.id)}
                  className="absolute top-2 right-1.5 inline-grid size-7 cursor-pointer place-items-center rounded-sm text-ink-faint opacity-0 transition-opacity group-hover:opacity-100 hover:text-destructive focus-visible:opacity-100"
                >
                  <Trash2 className="size-3.5" />
                </button>
              </li>
            ))
          )}
        </ul>
      </ScrollArea>
    </div>
  );
}

export function ChatPage() {
  const pricing = usePricing();
  const { balance, setBalance } = useSession();
  const [params, setParams] = useSearchParams();
  const conversationId = params.get("c");
  const [documents, setDocuments] = useState<AppDocument[] | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[] | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [draft, setDraft] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const [failure, setFailure] = useState<{ question: string; message: string; noCredits: boolean } | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [opened, setOpened] = useState<{ citation: Citation; doc?: AppDocument } | null>(null);
  const { stage, start, stop } = usePipelineStages();
  const elapsed = useElapsed(pendingQuestion !== null);
  const viewport = useRef<HTMLDivElement>(null);
  /* La conversation que l'on vient de créer en posant une question : pas besoin de la recharger. */
  const justCreated = useRef<string | null>(null);

  const loadConversations = useCallback(() => {
    appApi
      .conversations()
      .then((r) => setConversations(r.conversations))
      .catch(() => setConversations((c) => c ?? []));
  }, []);

  useEffect(() => {
    appApi
      .documents()
      .then((r) => setDocuments(r.documents))
      .catch((err) => {
        setDocuments([]);
        toast.error("Documents indisponibles", { description: errorMessage(err) });
      });
    loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    setFailure(null);
    if (!conversationId) {
      setMessages([]);
      return;
    }
    if (justCreated.current === conversationId) return;
    let alive = true;
    setLoadingConversation(true);
    appApi
      .conversation(conversationId)
      .then((c) => alive && setMessages(c.messages))
      .catch((err) => {
        if (!alive) return;
        toast.error("Conversation introuvable", { description: errorMessage(err) });
        setParams({}, { replace: true });
      })
      .finally(() => alive && setLoadingConversation(false));
    return () => {
      alive = false;
    };
  }, [conversationId, setParams]);

  useEffect(() => {
    const el = viewport.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages, pendingQuestion, stage, failure]);

  const ready = documents?.filter((d) => d.status === "ready") ?? [];
  const indexing = documents?.some((d) => d.status === "queued" || d.status === "processing") ?? false;

  /* Documents en cours d'indexation : on relit la liste pour les proposer dès qu'ils sont prêts. */
  useEffect(() => {
    if (!indexing) return;
    const id = setInterval(() => {
      appApi
        .documents()
        .then((r) => setDocuments(r.documents))
        .catch(() => undefined);
    }, 5000);
    return () => clearInterval(id);
  }, [indexing]);
  const canAfford = balance >= pricing.question_credits;
  const busy = pendingQuestion !== null;

  async function ask(text: string) {
    const q = text.trim();
    if (!q || busy || !ready.length) return;
    setDraft("");
    setFailure(null);
    setPendingQuestion(q);
    start();
    try {
      const r = await appApi.ask(q, conversationId);
      setMessages((m) => [...m, r.message]);
      setBalance(r.balance);
      if (r.conversation_id !== conversationId) {
        justCreated.current = r.conversation_id;
        setParams({ c: r.conversation_id });
      }
      loadConversations();
    } catch (err) {
      const noCredits = err instanceof ApiError && err.status === 402;
      setFailure({ question: q, message: errorMessage(err), noCredits });
      if (!noCredits) toast.error("Le pipeline a échoué", { description: errorMessage(err) });
    } finally {
      stop();
      setPendingQuestion(null);
    }
  }

  function selectConversation(id: string) {
    justCreated.current = null;
    setParams({ c: id });
    setHistoryOpen(false);
  }

  function newConversation() {
    justCreated.current = null;
    setParams({});
    setMessages([]);
    setHistoryOpen(false);
  }

  async function deleteConversation(id: string) {
    if (!window.confirm("Supprimer cette conversation ?")) return;
    try {
      await appApi.deleteConversation(id);
      setConversations((c) => c?.filter((x) => x.id !== id) ?? null);
      if (id === conversationId) newConversation();
    } catch (err) {
      toast.error("Suppression impossible", { description: errorMessage(err) });
    }
  }

  const openCitation = (c: Citation) => {
    const doc = documents ? citedDocument(c, documents) : undefined;
    if (c.pdf_url || doc || c.document_id) setOpened({ citation: c, doc });
    else toast.info("Ce passage ne peut pas être rouvert", { description: "Le document a peut-être été supprimé." });
  };

  const list = (
    <ConversationList
      conversations={conversations}
      activeId={conversationId}
      onSelect={selectConversation}
      onNew={newConversation}
      onDelete={deleteConversation}
    />
  );

  return (
    <div className="flex h-[calc(100dvh-3.5rem)] min-h-0 lg:h-full">
      <aside className="hidden w-64 shrink-0 border-r border-hairline bg-paper md:block">{list}</aside>

      {historyOpen ? (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="Historique">
          <button type="button" aria-label="Fermer" className="absolute inset-0 bg-ink/40" onClick={() => setHistoryOpen(false)} />
          <div className="rise-in absolute inset-y-0 left-0 w-[min(20rem,85vw)] border-r border-hairline bg-paper">
            <div className="flex justify-end p-2">
              <button
                type="button"
                aria-label="Fermer l'historique"
                onClick={() => setHistoryOpen(false)}
                className="inline-grid size-8 cursor-pointer place-items-center rounded-sm text-ink-muted"
              >
                <X className="size-4" />
              </button>
            </div>
            <div className="h-[calc(100%-3rem)]">{list}</div>
          </div>
        </div>
      ) : null}

      <section className="flex min-w-0 flex-1 flex-col bg-paper" aria-label="Conversation">
        <div className="flex items-center justify-between gap-3 border-b border-hairline px-4 py-2.5">
          <button
            type="button"
            onClick={() => setHistoryOpen(true)}
            className="mono-xs inline-flex cursor-pointer items-center gap-1.5 text-ink-muted hover:text-ink md:hidden"
          >
            <History className="size-3.5" /> Historique
          </button>
          <span className="meta truncate">
            {documents === null
              ? "chargement des documents…"
              : `${ready.length} document${ready.length > 1 ? "s" : ""} interrogé${ready.length > 1 ? "s" : ""}`}
            {indexing ? " · indexation en cours" : ""}
          </span>
          <span className="meta inline-flex shrink-0 items-center gap-1">
            <Coins className="size-3" /> {credits(pricing.question_credits)} / question
          </span>
        </div>

        <ScrollArea className="min-h-0 flex-1" viewportRef={viewport} data-lenis-prevent>
          <div className="mx-auto max-w-3xl space-y-5 p-5">
            {documents !== null && ready.length === 0 ? (
              <div className="rise-in card-paper p-8 text-center">
                <p className="display-sm">
                  {indexing ? "Vos documents sont en cours d'indexation" : "Ajoutez un document pour commencer"}
                </p>
                <p className="copy mx-auto mt-2 text-sm">
                  {indexing
                    ? "Dès qu'un document est prêt, vous pourrez l'interroger ici."
                    : `Déposez vos fichiers : ${pricing.free.documents} documents sont offerts avec l'offre gratuite.`}
                </p>
                <Button asChild variant="brand" className="mt-5">
                  <Link to="/app/documents">
                    {indexing ? "Suivre l'indexation" : "Déposer des documents"} <ArrowRight />
                  </Link>
                </Button>
              </div>
            ) : null}

            {ready.length > 0 && messages.length === 0 && !busy && !loadingConversation && !failure ? (
              <div className="rise-in py-6">
                <h2 className="display-sm">Que voulez-vous savoir ?</h2>
                <p className="copy mt-2 text-sm">
                  L'agent cherche dans {ready.length > 1 ? `vos ${ready.length} documents` : `« ${ready[0].name} »`}, lit les
                  pages utiles et répond en citant ses sources. Chaque question coûte {credits(pricing.question_credits)}.
                </p>
              </div>
            ) : null}

            {loadingConversation ? (
              <p className="meta inline-flex items-center gap-2">
                <Loader2 className="size-3.5 animate-spin" /> chargement de la conversation…
              </p>
            ) : null}

            {messages.map((m) => (
              <div key={m.id} className="space-y-5">
                <QuestionBubble>{m.question}</QuestionBubble>
                <AnswerBlock
                  answer={m.answer}
                  citations={m.citations}
                  signals={parseVerificationReport(m.verification_report)}
                  onOpen={openCitation}
                  meta={<span className="meta">{credits(m.credits)}</span>}
                  footer={
                    m.feedback_token ? (
                      <AnswerFeedback send={(score, comment) => appApi.feedback(m.feedback_token!, score, comment)} />
                    ) : null
                  }
                />
              </div>
            ))}

            {pendingQuestion ? (
              <>
                <QuestionBubble>{pendingQuestion}</QuestionBubble>
                <PipelineProgress stage={stage} elapsed={elapsed} />
              </>
            ) : null}

            {failure ? (
              <>
                <QuestionBubble>{failure.question}</QuestionBubble>
                <div role="alert" className="rise-in rounded-2xl border border-destructive/40 bg-destructive/5 px-4 py-3.5 text-sm">
                  <p className="text-destructive">{failure.message}</p>
                  {failure.noCredits ? (
                    <Link to="/app/credits" className="mono-xs mt-2 inline-block text-brand-deep hover:underline">
                      Recharger mes crédits →
                    </Link>
                  ) : (
                    <p className="meta mt-1">Les crédits réservés pour cette question vous ont été rendus.</p>
                  )}
                </div>
              </>
            ) : null}
          </div>
        </ScrollArea>

        <div className="border-t border-hairline p-3 sm:px-5">
          <div className="mx-auto max-w-3xl">
            {!canAfford && ready.length > 0 ? (
              <p className="mb-2 text-xs text-brand-deep">
                Solde insuffisant pour une question ({credits(balance)}).{" "}
                <Link to="/app/credits" className="font-medium underline">
                  Recharger
                </Link>
              </p>
            ) : null}
            <div className="flex items-end gap-2 rounded-sm border border-hairline-strong bg-paper p-2 transition-colors focus-within:border-brand">
              <textarea
                rows={1}
                value={draft}
                aria-label="Votre question"
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    if (canAfford) ask(draft);
                  }
                }}
                disabled={!ready.length || busy}
                placeholder={ready.length ? "Posez une question sur vos documents…" : "Aucun document prêt"}
                className="max-h-32 min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
              />
              <Button
                variant="brand"
                onClick={() => ask(draft)}
                disabled={!draft.trim() || !ready.length || busy || !canAfford}
                className="h-9 shrink-0 px-3.5"
              >
                Envoyer <ArrowRight />
              </Button>
            </div>
          </div>
        </div>
      </section>

      {opened ? (
        <DocumentViewer
          key={`${opened.citation.source}-${opened.citation.n}-${opened.citation.page}`}
          citation={opened.citation}
          url={opened.citation.pdf_url ? documentUrl(opened.citation.pdf_url) : opened.doc?.file_url ? documentUrl(opened.doc.file_url) : null}
          pageText={
            opened.doc || opened.citation.document_id
              ? (page) => appApi.pageText(opened.doc?.id ?? opened.citation.document_id!, page).then((r) => r.text)
              : undefined
          }
          onClose={() => setOpened(null)}
        />
      ) : null}
    </div>
  );
}
