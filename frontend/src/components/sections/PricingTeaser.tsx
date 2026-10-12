import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Section } from "@/components/site/primitives";
import { credits, euros, integer, usePricing } from "@/lib/session";

/** Section « Prix » de l'accueil : l'offre gratuite, le prix à l'usage, lien vers /tarifs. */
export function PricingTeaser() {
  const p = usePricing();
  const smallest = p.packs[0];
  const rows = [
    ["Une question, réponse citée", credits(p.question_credits), euros(p.question_credits * p.credit_value_eur)],
    ["Une page indexée", credits(p.page_credits), euros(p.page_credits * p.credit_value_eur)],
    ["Stockage, consultation, suppression", "gratuit", "—"],
  ];

  return (
    <Section
      id="prix"
      index="05"
      eyebrow="Prix"
      tone="muted"
      title={
        <>
          Payez ce que vous utilisez, <span className="accent-italic">au crédit</span>.
        </>
      }
      intro={`Commencez gratuitement avec ${p.free.documents} documents et ${integer(p.free.welcome_credits)} crédits offerts, sans carte. Rechargez ensuite à partir de ${euros(smallest?.price_eur ?? 10)} ; les crédits n'expirent pas.`}
    >
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-end">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="text-left">
              <th scope="col" className="mono-xs uppercase tracking-[0.09em] text-ink-faint pb-3 font-normal">Action</th>
              <th scope="col" className="mono-xs uppercase tracking-[0.09em] text-ink-faint pb-3 font-normal">Crédits</th>
              <th scope="col" className="mono-xs uppercase tracking-[0.09em] text-ink-faint pb-3 text-right font-normal">Prix TTC</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, cr, eur]) => (
              <tr key={label} className="border-t border-hairline">
                <td className="py-3.5 pr-4 text-ink">{label}</td>
                <td className="mono-xs py-3.5 pr-4 text-ink">{cr}</td>
                <td className="mono-xs py-3.5 text-right text-brand-deep">{eur}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="flex flex-col gap-3">
          <Button asChild variant="brand" size="lg">
            <Link to="/inscription">
              Commencer gratuitement <ArrowRight />
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/tarifs">Voir les tarifs</Link>
          </Button>
        </div>
      </div>
    </Section>
  );
}
