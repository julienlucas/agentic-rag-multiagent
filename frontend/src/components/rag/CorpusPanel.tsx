import { Link } from "react-router-dom";
import { ArrowRight, Check, FileText, Loader2, RefreshCw, TriangleAlert, Upload, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useElapsed } from "@/hooks/useTimer";
import { usePricing, useSession } from "@/lib/session";
import { exampleDocs } from "./examples";
import type { DocState } from "./types";

/** Une puce de document : exemple sélectionnable ou fichier uploadé. */
function DocChip({
  doc,
  active,
  onSelect,
  onRemove,
  onRetry,
}: {
  doc: DocState;
  active: boolean;
  onSelect?: () => void;
  onRemove?: () => void;
  onRetry?: () => void;
}) {
  const elapsed = useElapsed(doc.status === "loading");
  const clickable = !!onSelect && !active;

  return (
    <span
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      onClick={clickable ? onSelect : undefined}
      onKeyDown={
        clickable
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect?.();
              }
            }
          : undefined
      }
      className={cn(
        "inline-flex max-w-full items-center gap-2 rounded-full border px-3 py-1.5 text-xs transition-colors",
        active ? "border-brand bg-brand-surface text-ink" : "border-hairline bg-paper text-ink-muted",
        clickable && "cursor-pointer hover:border-brand hover:text-ink",
      )}
    >
      {doc.status === "loading" ? (
        <Loader2 className="size-3.5 shrink-0 animate-spin text-brand-deep" />
      ) : doc.status === "error" ? (
        <TriangleAlert className="size-3.5 shrink-0 text-destructive" />
      ) : active ? (
        <Check className="size-3.5 shrink-0 text-brand-deep" />
      ) : (
        <FileText className="size-3.5 shrink-0 text-muted-foreground" />
      )}

      <span className="min-w-0 truncate font-medium">{doc.title}</span>

      {doc.status === "loading" ? (
        <span className="meta">{elapsed}s</span>
      ) : doc.status === "error" && onRetry ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRetry();
          }}
          className="mono-xs inline-flex items-center gap-1 text-destructive hover:underline"
        >
          <RefreshCw className="size-3" /> réessayer
        </button>
      ) : (
        <span className="meta shrink-0 whitespace-nowrap">
          {doc.pages ? `${doc.pages} p.` : doc.kind}
        </span>
      )}

      {onRemove ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          aria-label={`Retirer ${doc.title}`}
          className="text-muted-foreground transition-colors hover:text-destructive"
        >
          <X className="size-3.5" />
        </button>
      ) : null}
    </span>
  );
}

/**
 * Colonne des documents de la démo : les exemples, et l'invitation à déposer ses propres
 * documents — ce qui demande un compte (20 documents offerts).
 */
export function CorpusPanel({
  active,
  onSelectExample,
  onRetry,
  busy,
}: {
  active: DocState | null;
  onSelectExample: (id: string) => void;
  onRetry: () => void;
  busy: boolean;
}) {
  const pricing = usePricing();
  const { status } = useSession();
  const signedIn = status === "authenticated";

  const examples: DocState[] = exampleDocs.map((ex) =>
    active?.id === ex.id
      ? active
      : {
          id: ex.id,
          title: ex.title,
          fileName: ex.fileName,
          kind: ex.kind,
          pages: ex.pages,
          type: ex.type,
          description: ex.description,
          source: "example",
          status: "idle",
        },
  );

  return (
    // Pleine hauteur de la conversation : l'invitation s'étire, les exemples restent en bas.
    <div className="flex flex-col gap-6 lg:flex-1">
      <div className="flex flex-col items-center justify-center gap-3 rounded-[var(--radius-media)] border border-dashed border-brand bg-paper px-4 py-8 text-center lg:flex-1">
        <span className="grid size-10 place-items-center rounded-full bg-brand-surface text-brand-deep [&_svg]:size-4.5">
          <Upload />
        </span>
        <div>
          <p className="text-sm font-medium text-ink">Vos propres documents</p>
          <p className="meta mt-1">
            {signedIn
              ? "PDF, Word, PowerPoint, images, tableurs…"
              : `${pricing.free.documents} documents offerts · sans carte`}
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link to={signedIn ? "/app/documents" : "/inscription"}>
            {signedIn ? "Ouvrir mes documents" : "Créer un compte gratuit"}
            <ArrowRight />
          </Link>
        </Button>
      </div>

      <div>
        <span className="meta">exemples de la démo</span>
        <div className="mt-3 flex flex-col items-start gap-2">
          {examples.map((d) => (
            <DocChip
              key={d.id}
              doc={d}
              active={active?.id === d.id}
              onSelect={busy ? undefined : () => onSelectExample(d.id)}
              onRetry={onRetry}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
