import { cn } from "@/lib/utils";
import { credits, euros, usePricing } from "@/lib/session";

/**
 * Puces de prix en Geist Mono : ce que coûte chaque action, en crédits et en euros.
 * Le prix est connu avant d'agir : c'est l'argument, on l'affiche tel quel.
 */
export function PriceChips({ className }: { className?: string }) {
  const p = usePricing();
  const chips = [
    { label: "Question", value: credits(p.question_credits), hint: euros(p.question_credits * p.credit_value_eur) },
    { label: "Page indexée", value: credits(p.page_credits), hint: euros(p.page_credits * p.credit_value_eur) },
    { label: "Stockage et consultation", value: "gratuit", hint: null },
    { label: "Pour commencer", value: `${p.free.documents} documents`, hint: "offerts" },
  ];
  return (
    <ul className={cn("flex flex-wrap justify-center gap-2", className)} aria-label="Prix à l'usage">
      {chips.map((c) => (
        <li
          key={c.label}
          className="inline-flex items-center gap-2 rounded-sm border border-hairline bg-paper px-3 py-1.5"
        >
          <span className="text-xs text-ink-muted">{c.label}</span>
          <span aria-hidden className="h-3 w-px bg-hairline-strong" />
          <span className="mono-xs text-ink">{c.value}</span>
          {c.hint ? <span className="mono-xs text-brand-deep">{c.hint}</span> : null}
        </li>
      ))}
    </ul>
  );
}
