import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { clearPendingUpload, peekPendingUpload } from "@/lib/pending-upload";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Eye, FileText, Loader2, Trash2, Upload, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { appApi, ApiError, documentUrl, type AppDocument, type Citation, type DocumentStatus } from "@/api";
import { DocumentViewer } from "@/components/rag/DocumentViewer";
import { errorMessage } from "@/lib/http";
import { countPdfPages } from "@/lib/pdf";
import { credits, integer, usePricing, useSession } from "@/lib/session";
import { cn } from "@/lib/utils";
import { PageHeader } from "./AppLayout";

const MAX_FILE_MB = 50;
const POLL_MS = 3000;

type Staged = { id: string; file: File; pages: number | null; counting: boolean };

const STATUS: Record<DocumentStatus, { label: string; dot: string }> = {
  queued: { label: "en file", dot: "bg-ink-faint" },
  processing: { label: "indexation", dot: "signal-dot bg-brand" },
  ready: { label: "prêt", dot: "bg-success" },
  error: { label: "erreur", dot: "bg-destructive" },
};

const extension = (name: string) => {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i).toLowerCase() : "";
};

const formatSize = (bytes: number) =>
  bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1).replace(".", ",")} Mo` : `${Math.max(1, Math.round(bytes / 1024))} Ko`;

const formatDate = (iso: string) =>
  new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(iso));

function Gauge({ label, value, max }: { label: string; value: number; max: number }) {
  const ratio = max > 0 ? Math.min(1, value / max) : 0;
  return (
    <div className="min-w-40">
      <div className="flex items-baseline justify-between gap-3">
        <span className="meta">{label}</span>
        <span className="mono-xs text-ink">
          {integer(value)} / {integer(max)}
        </span>
      </div>
      <div
        className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-paper-3"
        role="progressbar"
        aria-label={label}
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={max}
      >
        <div className={cn("h-full rounded-full", ratio >= 0.9 ? "bg-brand-strong" : "bg-brand")} style={{ width: `${ratio * 100}%` }} />
      </div>
    </div>
  );
}

export function DocumentsPage() {
  const pricing = usePricing();
  const { me, refresh, setBalance, balance } = useSession();
  const [documents, setDocuments] = useState<AppDocument[] | null>(null);
  const [staged, setStaged] = useState<Staged[]>([]);
  const [uploading, setUploading] = useState(false);
  const [rejected, setRejected] = useState<string[]>([]);
  const [opened, setOpened] = useState<AppDocument | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    try {
      const r = await appApi.documents();
      setDocuments(r.documents);
      return r.documents;
    } catch (err) {
      toast.error("Documents indisponibles", { description: errorMessage(err) });
      setDocuments((d) => d ?? []);
      return null;
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  /* Fichier déposé dans le hero de l'accueil avant l'inscription : prêt à indexer. */
  useEffect(() => {
    const files = peekPendingUpload();
    if (files.length) stage(files);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* Indexation en cours : on relit la liste toutes les 3 s, puis le compte quand tout est fini. */
  const inProgress = documents?.some((d) => d.status === "queued" || d.status === "processing") ?? false;
  useEffect(() => {
    if (!inProgress) return;
    const id = setInterval(async () => {
      const docs = await load();
      if (docs && !docs.some((d) => d.status === "queued" || d.status === "processing")) refresh();
    }, POLL_MS);
    return () => clearInterval(id);
  }, [inProgress, load, refresh]);

  /* ---------- sélection ---------- */

  const stage = (list: FileList | File[] | null) => {
    if (!list) return;
    const bad: string[] = [];
    const next: Staged[] = [];
    for (const file of Array.from(list)) {
      if (!pricing.formats.includes(extension(file.name))) bad.push(`${file.name} : format non pris en charge`);
      else if (file.size > MAX_FILE_MB * 1024 * 1024) bad.push(`${file.name} : plus de ${MAX_FILE_MB} Mo`);
      else next.push({ id: `${file.name}-${file.size}-${file.lastModified}`, file, pages: null, counting: extension(file.name) === ".pdf" });
    }
    setRejected(bad);
    setStaged((s) => [...s, ...next.filter((n) => !s.some((x) => x.id === n.id))]);
    next
      .filter((n) => n.counting)
      .forEach(async (n) => {
        const pages = await countPdfPages(n.file);
        setStaged((s) => s.map((x) => (x.id === n.id ? { ...x, pages, counting: false } : x)));
      });
  };

  const dragDepth = useRef(0);
  const [dragging, setDragging] = useState(false);
  const onDragEnter = (e: DragEvent) => {
    if (!e.dataTransfer.types.includes("Files")) return;
    e.preventDefault();
    dragDepth.current += 1;
    setDragging(true);
  };
  const onDragLeave = (e: DragEvent) => {
    e.preventDefault();
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) setDragging(false);
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    dragDepth.current = 0;
    setDragging(false);
    if (!uploading) stage(e.dataTransfer.files);
  };

  /* ---------- coût estimé ---------- */

  const free = me?.workspace.plan === "free";
  const knownPages = staged.reduce((n, s) => n + (s.pages ?? 0), 0);
  const unknown = staged.filter((s) => s.pages == null && !s.counting).length;
  const counting = staged.some((s) => s.counting);
  const estimate = free ? 0 : knownPages * pricing.page_credits;
  const docsLeft = me ? me.workspace.max_documents - me.workspace.documents_count : Infinity;
  const overQuota = staged.length > docsLeft;

  async function upload() {
    if (!staged.length) return;
    setUploading(true);
    try {
      const r = await appApi.upload(staged.map((s) => s.file));
      setBalance(r.balance);
      setStaged([]);
      clearPendingUpload();
      setDocuments((docs) => {
        const ids = new Set(r.documents.map((d) => d.id));
        return [...r.documents, ...(docs ?? []).filter((d) => !ids.has(d.id))];
      });
      toast.success(r.documents.length > 1 ? `${r.documents.length} documents en cours d'indexation` : "Document en cours d'indexation");
      refresh();
    } catch (err) {
      if (err instanceof ApiError && err.status === 402) {
        toast.error("Crédits insuffisants", {
          description: err.message,
          action: { label: "Recharger", onClick: () => navigate("/app/credits") },
        });
      } else {
        toast.error("Envoi impossible", { description: errorMessage(err) });
      }
    } finally {
      setUploading(false);
    }
  }

  async function remove(doc: AppDocument) {
    if (!window.confirm(`Supprimer « ${doc.name} » ? Le fichier et son index seront effacés.`)) return;
    try {
      await appApi.deleteDocument(doc.id);
      setDocuments((docs) => docs?.filter((d) => d.id !== doc.id) ?? null);
      refresh();
    } catch (err) {
      toast.error("Suppression impossible", { description: errorMessage(err) });
    }
  }

  return (
    <div className="h-full overflow-y-auto" data-lenis-prevent>
      <div className="mx-auto max-w-6xl space-y-8 px-4 py-8 sm:px-8">
        <PageHeader eyebrow="Espace" title="Documents">
          {me ? (
            <div className="flex flex-wrap gap-6">
              <Gauge label="documents" value={me.workspace.documents_count} max={me.workspace.max_documents} />
              <Gauge label="pages" value={me.workspace.pages_count} max={me.workspace.max_pages} />
            </div>
          ) : null}
        </PageHeader>

        {/* ---------- dépôt ---------- */}
        <section aria-label="Ajouter des documents" className="card-paper p-5">
          <input
            ref={fileInput}
            type="file"
            multiple
            accept={pricing.formats.join(",")}
            className="hidden"
            onChange={(e) => {
              stage(e.target.files);
              e.target.value = "";
            }}
          />
          <div
            onDragEnter={onDragEnter}
            onDragOver={(e) => e.preventDefault()}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            className={cn(
              "flex flex-col items-center justify-center gap-3 rounded-[var(--radius-media)] border border-dashed px-4 py-10 text-center transition-colors",
              dragging ? "border-brand bg-brand-surface" : "border-hairline-strong bg-paper-2",
            )}
          >
            <span className="grid size-10 place-items-center rounded-full bg-brand-surface text-brand-deep [&_svg]:size-4.5">
              <Upload />
            </span>
            <div>
              <p className="text-sm font-medium text-ink">{dragging ? "Déposez les fichiers" : "Glissez vos documents ici"}</p>
              <p className="meta mt-1">
                PDF, Word, PowerPoint, images, texte, tableurs · {MAX_FILE_MB} Mo max par fichier
              </p>
            </div>
            <Button variant="outline" size="sm" disabled={uploading} onClick={() => fileInput.current?.click()}>
              Choisir des fichiers
            </Button>
          </div>

          {rejected.length ? (
            <ul className="mt-3 space-y-1 text-xs text-destructive" role="alert">
              {rejected.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          ) : null}

          {staged.length ? (
            <div className="mt-5">
              <ul className="divide-y divide-hairline border-y border-hairline">
                {staged.map((s) => (
                  <li key={s.id} className="flex items-center gap-3 py-2.5 text-sm">
                    <FileText className="size-4 shrink-0 text-ink-faint" />
                    <span className="min-w-0 flex-1 truncate">{s.file.name}</span>
                    <span className="meta shrink-0">{formatSize(s.file.size)}</span>
                    <span className="mono-xs w-24 shrink-0 text-right text-ink">
                      {s.counting ? "…" : s.pages != null ? `${s.pages} p.` : "au nb de pages"}
                    </span>
                    <button
                      type="button"
                      aria-label={`Retirer ${s.file.name}`}
                      disabled={uploading}
                      onClick={() => {
                        clearPendingUpload();
                        setStaged((list) => list.filter((x) => x.id !== s.id));
                      }}
                      className="inline-grid size-7 cursor-pointer place-items-center rounded-sm text-ink-faint hover:text-destructive"
                    >
                      <X className="size-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-ink-muted">
                  {free ? (
                    <>Indexation offerte avec l'offre gratuite{knownPages ? ` · ${integer(knownPages)} pages` : ""}.</>
                  ) : (
                    <>
                      Coût estimé : <span className="mono-xs text-ink">{credits(estimate)}</span>
                      {unknown ? ` + ${credits(pricing.page_credits)} par page pour ${unknown} fichier${unknown > 1 ? "s" : ""} non PDF` : ""}
                      {" · "}solde {credits(balance)}
                    </>
                  )}
                  {overQuota ? (
                    <span className="mt-1 block text-destructive">
                      Il vous reste {Math.max(0, docsLeft)} document{docsLeft > 1 ? "s" : ""} dans votre quota.
                    </span>
                  ) : null}
                </p>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" disabled={uploading} onClick={() => {
                    clearPendingUpload();
                    setStaged([]);
                  }}>
                    Annuler
                  </Button>
                  <Button variant="brand" size="sm" disabled={uploading || counting || overQuota} onClick={upload}>
                    {uploading ? (
                      <>
                        <Loader2 className="animate-spin" /> Envoi…
                      </>
                    ) : free ? (
                      <>
                        Indexer {staged.length} fichier{staged.length > 1 ? "s" : ""} <ArrowRight />
                      </>
                    ) : (
                      <>
                        Indexer : {credits(estimate)}
                        {unknown ? " +" : ""} <ArrowRight />
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          ) : null}
        </section>

        {/* ---------- liste ---------- */}
        <section aria-label="Vos documents">
          {documents === null ? (
            <p className="meta inline-flex items-center gap-2">
              <Loader2 className="size-3.5 animate-spin" /> chargement…
            </p>
          ) : documents.length === 0 ? (
            <div className="card-paper p-8 text-center">
              <p className="display-sm">Aucun document pour l'instant</p>
              <p className="copy mx-auto mt-2 text-sm">
                Déposez un premier fichier ci-dessus : dès qu'il est prêt, posez-lui vos questions dans le chat.
              </p>
            </div>
          ) : (
            <div className="card-paper overflow-x-auto">
              <table className="w-full min-w-[44rem] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-hairline text-left">
                    {["Nom", "Type", "Pages", "Statut", "Ajouté", "Crédits", ""].map((h, i) => (
                      <th key={i} scope="col" className="mono-xs uppercase tracking-[0.09em] text-ink-faint px-4 py-3 font-normal">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {documents.map((d) => {
                    const st = STATUS[d.status];
                    return (
                      <tr key={d.id} className="border-b border-hairline last:border-0">
                        <td className="max-w-[18rem] px-4 py-3">
                          <span className="block truncate font-medium text-ink" title={d.name}>
                            {d.name}
                          </span>
                          {d.status === "error" && d.error ? (
                            <span className="block text-xs text-destructive">{d.error}</span>
                          ) : null}
                        </td>
                        <td className="mono-xs px-4 py-3 uppercase text-ink-muted">{d.kind}</td>
                        <td className="mono-xs px-4 py-3 text-ink">{d.pages ? integer(d.pages) : "—"}</td>
                        <td className="px-4 py-3">
                          <span className="inline-flex items-center gap-2 text-xs text-ink-muted">
                            <span aria-hidden className={cn("size-2 rounded-full", st.dot)} />
                            {st.label}
                          </span>
                        </td>
                        <td className="mono-xs whitespace-nowrap px-4 py-3 text-ink-muted">{formatDate(d.created_at)}</td>
                        <td className="mono-xs px-4 py-3 text-ink">{integer(d.credits)}</td>
                        <td className="px-4 py-3">
                          <div className="flex justify-end gap-1">
                            <button
                              type="button"
                              aria-label={`Ouvrir ${d.name}`}
                              title="Ouvrir"
                              disabled={d.status !== "ready"}
                              onClick={() => setOpened(d)}
                              className="inline-grid size-8 cursor-pointer place-items-center rounded-sm text-ink-muted hover:bg-brand-surface hover:text-ink disabled:cursor-not-allowed disabled:opacity-35"
                            >
                              <Eye className="size-4" />
                            </button>
                            <button
                              type="button"
                              aria-label={`Supprimer ${d.name}`}
                              title="Supprimer"
                              onClick={() => remove(d)}
                              className="inline-grid size-8 cursor-pointer place-items-center rounded-sm text-ink-muted hover:bg-destructive/10 hover:text-destructive"
                            >
                              <Trash2 className="size-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          {documents?.some((d) => d.status === "ready") ? (
            <p className="mt-4 text-sm text-ink-muted">
              <Link to="/app/chat" className="font-medium text-brand-deep hover:underline">
                Poser une question sur vos documents →
              </Link>
            </p>
          ) : null}
        </section>
      </div>

      {opened ? (
        <DocumentViewer
          key={opened.id}
          citation={{ n: 0, source: opened.name, page: 1, locator: opened.name, excerpt: "" } satisfies Citation}
          url={opened.file_url ? documentUrl(opened.file_url) : null}
          pageText={(page) => appApi.pageText(opened.id, page).then((r) => r.text)}
          subtitle={`${opened.kind.toUpperCase()} · ${opened.pages} pages`}
          onClose={() => setOpened(null)}
        />
      ) : null}
    </div>
  );
}
