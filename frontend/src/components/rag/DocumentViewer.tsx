import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, ExternalLink, FileText, X } from "lucide-react";
import type { PDFDocumentProxy } from "pdfjs-dist";
import type { TextItem } from "pdfjs-dist/types/src/display/api";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { api, documentUrl, type Citation } from "@/api";
import { matchSegments } from "@/lib/passage";
import { cn } from "@/lib/utils";

/*
 * Ouvre le document d'une citation à la page citée et y surligne le passage.
 *
 * Source, dans l'ordre : l'original servi par l'URL de la citation (exemple ou dépôt
 * conservé), le fichier encore en mémoire s'il vient d'être déposé, sinon le texte OCR de
 * la page lu dans l'index (documents déposés avant que les originaux soient conservés).
 */

type Box = { left: number; top: number; width: number; height: number };

async function loadPdfjs() {
  const pdfjs = await import("pdfjs-dist");
  pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;
  return pdfjs;
}

export function DocumentViewer({
  citation,
  sessionId,
  file,
  onClose,
}: {
  citation: Citation;
  sessionId: string;
  /** Fichier déposé pendant la session, s'il correspond au document cité. */
  file?: File;
  onClose: () => void;
}) {
  const cited = citation.page ?? 1;
  const [page, setPage] = useState(cited);
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [mode, setMode] = useState<"loading" | "pdf" | "text" | "error">("loading");
  const [text, setText] = useState<string | null>(null);
  const [width, setWidth] = useState(0);
  const [boxes, setBoxes] = useState<Box[]>([]);
  const [rendering, setRendering] = useState(false);
  const frame = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const firstMark = useRef<HTMLElement | null>(null);
  const passage = citation.text || citation.excerpt;
  const url = citation.pdf_url ? documentUrl(citation.pdf_url, sessionId) : null;
  const pageCount = pdf?.numPages ?? null;

  /* Échap ferme le panneau. */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  /* Chargement du PDF, avec repli sur le texte OCR. */
  useEffect(() => {
    let cancelled = false;
    let loaded: PDFDocumentProxy | null = null;
    (async () => {
      try {
        if (!url && !file) throw new Error("pas d'original");
        const pdfjs = await loadPdfjs();
        const source = url
          ? { url, disableRange: true, disableStream: true }
          : { data: new Uint8Array(await file!.arrayBuffer()) };
        loaded = await pdfjs.getDocument(source).promise;
        if (cancelled) return;
        setPdf(loaded);
        setMode("pdf");
      } catch {
        if (!cancelled) setMode(citation.file_hash ? "text" : "error");
      }
    })();
    return () => {
      cancelled = true;
      loaded?.destroy();
    };
  }, [url, file, citation.file_hash]);

  /* Repli : texte OCR de la page affichée. */
  useEffect(() => {
    if (mode !== "text" || !citation.file_hash) return;
    let cancelled = false;
    setText(null);
    api
      .pageText(citation.file_hash, page, sessionId)
      .then((r) => !cancelled && setText(r.text))
      .catch(() => !cancelled && setText(""));
    return () => {
      cancelled = true;
    };
  }, [mode, page, citation.file_hash, sessionId]);

  /* Largeur disponible : la page est rendue à la largeur du panneau. */
  useLayoutEffect(() => {
    const el = frame.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    setWidth(el.clientWidth);
    return () => ro.disconnect();
  }, [mode]);

  /* Rendu de la page, et des zones surlignées sur la page citée. */
  useEffect(() => {
    if (!pdf || !width || !canvas.current) return;
    let cancelled = false;
    let task: { cancel: () => void; promise: Promise<void> } | null = null;
    (async () => {
      setRendering(true);
      firstMark.current = null;
      const pdfjs = await loadPdfjs();
      const p = await pdf.getPage(Math.min(Math.max(page, 1), pdf.numPages));
      const base = p.getViewport({ scale: 1 });
      const viewport = p.getViewport({ scale: width / base.width });
      const ratio = window.devicePixelRatio || 1;
      const c = canvas.current;
      if (cancelled || !c) return;
      c.width = Math.floor(viewport.width * ratio);
      c.height = Math.floor(viewport.height * ratio);
      c.style.width = `${viewport.width}px`;
      c.style.height = `${viewport.height}px`;
      const ctx = c.getContext("2d");
      if (!ctx) return;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      task = p.render({ canvasContext: ctx, viewport });
      try {
        await task.promise;
      } catch {
        return; // rendu annulé par un changement de page
      }
      if (cancelled) return;

      if (page !== cited) {
        setBoxes([]);
      } else {
        const content = await p.getTextContent();
        const items = content.items.filter((it): it is TextItem => "str" in it);
        const marked = matchSegments(
          items.map((it) => it.str),
          passage,
        );
        setBoxes(
          items
            .filter((_, i) => marked[i])
            .map((it) => {
              const tx = pdfjs.Util.transform(viewport.transform, it.transform);
              const height = Math.hypot(tx[2], tx[3]);
              return { left: tx[4], top: tx[5] - height, width: it.width * viewport.scale, height };
            }),
        );
      }
      setRendering(false);
    })();
    return () => {
      cancelled = true;
      task?.cancel();
    };
  }, [pdf, page, width, cited, passage]);

  /* Amène le passage surligné à l'écran. */
  useEffect(() => {
    firstMark.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [boxes, text]);

  const lines = text?.split("\n") ?? [];
  const markedLines = page === cited ? matchSegments(lines, passage) : lines.map(() => false);
  const firstLine = markedLines.indexOf(true);
  const lastPage = pageCount ?? Number.POSITIVE_INFINITY;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label={citation.locator}>
      <button type="button" aria-label="Fermer" onClick={onClose} className="absolute inset-0 bg-ink/40 cursor-default" />
      <div className="rise-in relative flex h-full w-full flex-col border-l border-hairline-strong bg-paper shadow-2xl sm:w-[min(52rem,92vw)]">
        <header className="flex items-center gap-3 border-b border-hairline px-4 py-3">
          <FileText className="size-4 shrink-0 text-brand-deep" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{citation.locator}</p>
            <p className="meta">
              {mode === "text"
                ? "texte OCR de la page (original indisponible)"
                : `passage [${citation.n}] surligné sur la page citée`}
            </p>
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              aria-label="Page précédente"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="inline-grid size-8 cursor-pointer place-items-center rounded-sm text-ink-muted hover:bg-brand-surface disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ChevronLeft className="size-4" />
            </button>
            <span className="mono-xs min-w-16 text-center text-ink-muted">
              p. {page}
              {pageCount ? ` / ${pageCount}` : ""}
            </span>
            <button
              type="button"
              aria-label="Page suivante"
              disabled={page >= lastPage}
              onClick={() => setPage((p) => p + 1)}
              className="inline-grid size-8 cursor-pointer place-items-center rounded-sm text-ink-muted hover:bg-brand-surface disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ChevronRight className="size-4" />
            </button>
            {url && mode === "pdf" ? (
              <a
                href={`${url}#page=${page}`}
                target="_blank"
                rel="noreferrer"
                aria-label="Ouvrir le PDF dans un nouvel onglet"
                title="Ouvrir le PDF dans un nouvel onglet"
                className="inline-grid size-8 place-items-center rounded-sm text-ink-muted hover:bg-brand-surface"
              >
                <ExternalLink className="size-4" />
              </a>
            ) : null}
            <button
              type="button"
              aria-label="Fermer"
              onClick={onClose}
              className="inline-grid size-8 cursor-pointer place-items-center rounded-sm text-ink-muted hover:bg-brand-surface"
            >
              <X className="size-4" />
            </button>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto bg-brand-surface/40 p-4" data-lenis-prevent>
          <div ref={frame} className="mx-auto w-full max-w-[48rem]">
            {mode === "loading" ? <p className="meta">ouverture du document…</p> : null}
            {mode === "error" ? (
              <p className="text-sm text-muted-foreground">
                Ce document ne peut pas être rouvert : déposez-le à nouveau pour en garder l'original.
              </p>
            ) : null}

            {mode === "pdf" ? (
              <div className={cn("relative bg-white shadow-sm transition-opacity", rendering && "opacity-60")}>
                <canvas ref={canvas} className="block" />
                {boxes.map((b, i) => (
                  <span
                    key={i}
                    ref={i === 0 ? (el) => void (firstMark.current = el) : undefined}
                    className="pointer-events-none absolute rounded-[2px] bg-brand/40 mix-blend-multiply"
                    style={{ left: b.left - 1, top: b.top - 1, width: b.width + 2, height: b.height + 2 }}
                  />
                ))}
              </div>
            ) : null}

            {mode === "text" ? (
              text === null ? (
                <p className="meta">lecture de la page…</p>
              ) : text === "" ? (
                <p className="text-sm text-muted-foreground">Page introuvable dans l'index.</p>
              ) : (
                <div className="whitespace-pre-wrap rounded-sm bg-white p-5 font-mono text-[0.72rem] leading-relaxed text-ink shadow-sm">
                  {lines.map((line, i) =>
                    markedLines[i] ? (
                      <mark
                        key={i}
                        ref={i === firstLine ? (el) => void (firstMark.current = el) : undefined}
                        className="block bg-brand/35 text-ink"
                      >
                        {line || " "}
                      </mark>
                    ) : (
                      <span key={i} className="block">
                        {line || " "}
                      </span>
                    ),
                  )}
                </div>
              )
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
