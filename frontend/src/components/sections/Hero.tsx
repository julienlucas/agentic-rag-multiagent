import { useRef, useState, type DragEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, ArrowUp, FileText, Plus } from "lucide-react";
import { Container } from "@/components/site/primitives";
import { setPendingUpload } from "@/lib/pending-upload";
import { credits, euros, integer, usePricing, useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

/*
 * Hero, sur le modèle d'agentik.cc : un titre centré dont le mot clé est souligné d'un trait
 * orange, une phrase, puis un seul geste — le champ « Insérez votre premier document ».
 * Le fichier choisi est gardé en mémoire (lib/pending-upload) : connecté, on l'indexe depuis
 * Documents ; sinon on passe par l'inscription, et il attend dans Documents.
 */

const FORMAT_BADGES = ["PDF", "Word", "PowerPoint", "Excel", "Images", "Texte"];

function HandUnderline() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 300 16"
      preserveAspectRatio="none"
      className="hand-underline pointer-events-none absolute -bottom-[0.14em] left-0 h-[0.2em] w-full overflow-visible text-brand"
    >
      <path
        d="M3 11.5C58 6.2 122 3.6 183 4.4c40 .5 77 2.6 114 6.4"
        pathLength={1}
        fill="none"
        stroke="currentColor"
        strokeWidth="7"
        strokeLinecap="round"
      />
    </svg>
  );
}

function Ticker() {
  const p = usePricing();
  const items: [string, string][] = [
    ["Réponses correctes", "88,1 % · FinanceBench"],
    ["Question", `${credits(p.question_credits)} · ${euros(p.question_credits * p.credit_value_eur)}`],
    ["Page indexée", `${credits(p.page_credits)} · ${euros(p.page_credits * p.credit_value_eur)}`],
    ["Pages indexées ensemble", "12 000"],
    ["Pour commencer", `${p.free.documents} documents offerts`],
    ["Citations", "ouvertes à la page"],
    ["Outils de l'agent", "search · grep · read_page · navigate"],
    ["Données", "hébergées en UE"],
    ["Formats", "PDF · DOCX · PPTX · XLSX · images"],
  ];
  const row = (hidden: boolean) => (
    <ul className="flex shrink-0 items-center" aria-hidden={hidden || undefined}>
      {items.map(([label, value]) => (
        <li key={label} className="flex items-center gap-2.5 px-6 py-4 whitespace-nowrap">
          <span aria-hidden className="size-1.5 rounded-full bg-brand" />
          <span className="text-sm text-ink">{label}</span>
          <span className="mono-xs text-ink-muted">{value}</span>
        </li>
      ))}
    </ul>
  );
  return (
    <div className="ticker overflow-hidden border-y border-hairline bg-paper">
      <div className="ticker-track">
        {row(false)}
        {row(true)}
      </div>
    </div>
  );
}

export function Hero() {
  const pricing = usePricing();
  const { status } = useSession();
  const navigate = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const signedIn = status === "authenticated";

  const take = (list: FileList | null) => {
    const files = Array.from(list ?? []);
    if (!files.length) return;
    setPendingUpload(files);
    navigate(signedIn ? "/app/documents" : "/inscription?next=%2Fapp%2Fdocuments");
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    take(e.dataTransfer.files);
  };

  return (
    <section id="top" className="relative overflow-hidden bg-paper">
      {/* Trame de points très légère : de la profondeur sans image. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 [background-image:radial-gradient(var(--hairline-strong)_1px,transparent_1px)] [background-size:24px_24px] [mask-image:radial-gradient(ellipse_at_center,#000_20%,transparent_70%)] opacity-60"
      />
      <Container className="relative pt-20 pb-16 text-center sm:pt-28 sm:pb-24">
        <p className="mono-xs mx-auto inline-flex items-center gap-2 rounded-full border border-hairline bg-paper px-3 py-1 text-ink-muted">
          <span className="size-1.5 rounded-full bg-success" aria-hidden />
          88,1 % de bonnes réponses · FinanceBench
        </p>

        <h1 className="display-xl mx-auto mt-7 max-w-4xl">
          Posez vos questions à{" "}
          <span className="relative inline-block whitespace-nowrap">
            vos documents
            <HandUnderline />
          </span>
        </h1>

        <p className="mx-auto mt-7 max-w-2xl text-lg leading-relaxed text-ink-muted sm:text-xl">
          Un agent qui cherche, lit les pages entières et cite ses sources, page à l'appui.
          Rapports, contrats, présentations, tableurs : jusqu'à des milliers de pages interrogées ensemble.
        </p>

        <div className="mx-auto mt-12 max-w-xl">
          <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2">
            <span className="display-sm">Insérez votre premier document</span>
            <ul className="flex flex-wrap justify-center gap-1" aria-label="Formats acceptés">
              {FORMAT_BADGES.map((f) => (
                <li key={f} className="mono-xs rounded-sm border border-hairline px-1.5 py-0.5 text-ink-faint">
                  {f}
                </li>
              ))}
            </ul>
          </div>

          <div
            role="button"
            tabIndex={0}
            aria-label="Insérez votre premier document : choisir un fichier"
            onClick={() => input.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                input.current?.click();
              }
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={cn(
              "group mt-5 flex cursor-pointer items-center gap-3 rounded-[10px] border bg-paper p-2 pl-4 text-left",
              "shadow-[0_1px_0_var(--hairline),0_18px_40px_-18px_color-mix(in_srgb,var(--ink)_28%,transparent)]",
              "transition-[border-color,box-shadow] duration-[var(--dur-fast)]",
              dragging ? "border-brand ring-4 ring-brand-surface" : "border-hairline-strong hover:border-brand",
            )}
          >
            <Plus className="size-4 shrink-0 text-ink-faint transition-colors group-hover:text-brand-deep" aria-hidden />
            <span className="min-w-0 flex-1 truncate text-[0.975rem] text-ink-muted">
              {dragging ? "Déposez le fichier ici" : "Insérez votre premier document…"}
            </span>
            <span className="mono-xs hidden text-ink-faint sm:inline">ou glissez-le ici</span>
            <span
              aria-hidden
              className="inline-flex size-10 shrink-0 items-center justify-center rounded-[7px] bg-ink text-paper transition-colors group-hover:bg-brand group-hover:text-on-brand"
            >
              <ArrowUp className="size-4" />
            </span>
          </div>
          <input
            ref={input}
            type="file"
            multiple
            className="sr-only"
            tabIndex={-1}
            accept={pricing.formats.join(",")}
            onChange={(e) => take(e.target.files)}
          />

          <p className="meta mt-4">
            {integer(pricing.free.documents)} documents et {integer(pricing.free.welcome_credits)} crédits offerts ·
            sans carte bancaire
          </p>
          <p className="mt-6 text-sm text-ink-muted">
            <FileText className="mr-1.5 inline size-3.5 align-[-2px] text-ink-faint" aria-hidden />
            Ou essayez d'abord{" "}
            <Link to="/demo" className="font-medium text-ink underline decoration-hairline-strong underline-offset-4 hover:text-brand-deep hover:decoration-current">
              la démo sur les 10-K d'AMD et de Boeing
            </Link>
            <ArrowRight className="ml-1 inline size-3.5 align-[-2px] text-ink-faint" aria-hidden />
          </p>
        </div>
      </Container>
      <Ticker />
    </section>
  );
}
