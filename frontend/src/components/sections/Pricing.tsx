import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Section } from "@/components/site/primitives";
import { credits, euros, integer, usePricing, useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

/*
 * 02 · Prix, sur le modèle d'agentik.cc/pricing : deux offres, ce qui est inclus, un exemple de
 * recharge, et ce que coûte l'indexation d'1 Go. Chiffres lus sur GET /api/pricing.
 *
 * 1 Go → pages : mesuré sur les 84 PDF de FinanceBench (165 Mo pour 12 013 pages, ≈ 14 Ko par
 * page). Un PDF illustré ou scanné pèse bien plus par page : le poids ne dit pas le prix, les pages si.
 */
const GB_PROFILES = [
  { kind: "PDF texte", example: "rapports annuels, contrats, notes", kbPerPage: 14 },
  { kind: "PDF illustrés", example: "présentations, plaquettes, graphiques", kbPerPage: 100 },
  { kind: "Documents scannés", example: "courriers, factures numérisées", kbPerPage: 250 },
];

function Plan({
  name, price, note, text, rows, cta,
}: { name: string; price: ReactNode; note: string; text: string; rows: [string, string][]; cta: ReactNode }) {
  return (
    <div className="card-paper flex flex-col p-6 sm:p-8">
      <h3 className="display-sm">{name}</h3>
      <p className="mt-6 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-display text-[clamp(2.5rem,2rem+1.5vw,3.25rem)] leading-none font-semibold tracking-[-0.04em]">{price}</span>
        <span className="text-ink-muted">{note}</span>
      </p>
      <p className="mt-5 leading-relaxed text-ink-muted">{text}</p>
      <dl className="mt-6 space-y-4 border-t border-hairline pt-6">
        {rows.map(([k, v]) => (
          <div key={k}>
            <dt className="meta">{k}</dt>
            <dd className="mt-1 text-ink">{v}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-auto pt-8">{cta}</div>
    </div>
  );
}

export function Pricing() {
  const p = usePricing();
  const { status } = useSession();
  const signedIn = status === "authenticated";
  const [packId, setPackId] = useState<string>(p.packs[3]?.id ?? p.packs[0]?.id ?? "");
  const pack = p.packs.find((x) => x.id === packId) ?? p.packs[0];
  const questionEur = p.question_credits * p.credit_value_eur;
  const pageEur = p.page_credits * p.credit_value_eur;
  const base = pack ? Math.round(pack.price_eur / p.credit_value_eur) : 0;
  const bonus = pack ? pack.credits - base : 0;

  const cta = (label: string, variant: "brand" | "outline") => (
    <Button asChild variant={variant} size="lg">
      <Link to={signedIn ? "/app/credits" : "/inscription"}>
        {signedIn ? "Ouvrir mes crédits" : label} <ArrowRight />
      </Link>
    </Button>
  );

  const included: [string, string, string][] = [
    ["Documents", `${p.free.documents}`, `jusqu'à ${integer(p.paid.documents)}`],
    ["Pages indexées", `${integer(p.free.pages)} au total`, `jusqu'à ${integer(p.paid.pages)}`],
    ["Indexation", "Offerte", `${credits(p.page_credits)} par page (${euros(pageEur, 2)})`],
    ["Questions", `${integer(p.free.welcome_credits)} crédits offerts, ≈ ${integer(p.free.welcome_credits / p.question_credits)} questions`, `${credits(p.question_credits)} par question (${euros(questionEur, 2)})`],
    ["Formats", "PDF, Word, PowerPoint, Excel, images, texte", "Les mêmes"],
    ["Citations", "Ouvertes dans le document, à la page", "Les mêmes"],
    ["Stockage et consultation", "Gratuits", "Gratuits"],
    ["Données", "Hébergées en UE, isolées par compte", "Les mêmes"],
    ["Paiement", "Aucune carte", "Carte, recharges prépayées sans abonnement"],
  ];

  return (
    <Section
      id="prix"
      index="02"
      eyebrow="Prix"
      title={
        <>
          0 € pour commencer. Ensuite, vous payez <span className="accent-italic">ce que vous utilisez</span>.
        </>
      }
      intro={<p>Pas d'abonnement : un solde de crédits prépayé, débité à chaque page indexée et à chaque question.</p>}
    >
      <div className="grid gap-5 lg:grid-cols-2">
        <Plan
          name="Gratuit"
          price="0 €"
          note="sans carte"
          text={`Créez votre espace et déposez vos premiers documents. ${integer(p.free.welcome_credits)} crédits offerts pour vos premières questions.`}
          rows={[
            ["Pour commencer", `${p.free.documents} documents, ${integer(p.free.pages)} pages, indexation offerte`],
            ["Engagement", "Aucun"],
          ]}
          cta={cta("Créer mon espace", "brand")}
        />
        <Plan
          name="À la carte"
          price={euros(p.credit_value_eur, 2)}
          note="le crédit, prépayé"
          text="Rechargez quand vous voulez : chaque page indexée et chaque question se paient sur le même solde. Les crédits n'expirent pas."
          rows={[
            ["À l'usage", `Question : ${credits(p.question_credits)} · page indexée : ${credits(p.page_credits)}`],
            ["Recharges", `De ${euros(p.packs[0]?.price_eur ?? 10)} à ${euros(p.packs[p.packs.length - 1]?.price_eur ?? 100)}, jusqu'à +10 % de crédits`],
          ]}
          cta={cta("Créer mon espace", "outline")}
        />
      </div>

      <h3 className="display-sm mt-20">Ce qui est inclus</h3>
      <div className="mt-6 overflow-x-auto rounded-[var(--radius-media)] border border-hairline">
        <table className="w-full min-w-[36rem] text-left text-sm">
          <thead className="bg-paper-2">
            <tr>
              <th scope="col" className="w-1/4 px-5 py-3.5 font-normal" />
              <th scope="col" className="px-5 py-3.5 font-medium text-ink">Gratuit</th>
              <th scope="col" className="px-5 py-3.5 font-medium text-ink">À la carte</th>
            </tr>
          </thead>
          <tbody>
            {included.map(([k, free, paid]) => (
              <tr key={k} className="border-t border-hairline">
                <th scope="row" className="px-5 py-3.5 font-normal text-ink-muted">{k}</th>
                <td className="px-5 py-3.5 text-ink">{free}</td>
                <td className="px-5 py-3.5 text-ink">{paid}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-20 grid items-start gap-10 lg:grid-cols-2">
        <div>
          <h3 className="display-sm">Le prix avant l'action</h3>
          <p className="copy mt-3">
            Un crédit vaut {euros(p.credit_value_eur, 2)} TTC. Vous voyez ce que coûte une indexation avant de la lancer,
            et votre solde reste visible dans l'app.
          </p>
          <ul className="mt-6 space-y-3">
            {[
              "Le coût s'affiche avant d'indexer : « Indexer : 142 crédits ».",
              "Une indexation ou une question qui échoue est remboursée.",
              "Un même fichier n'est jamais facturé deux fois.",
              "Les crédits n'expirent pas ; stockage et consultation sont gratuits.",
            ].map((t) => (
              <li key={t} className="flex gap-2.5 text-ink">
                <Check className="mt-1 size-4 shrink-0 text-brand-deep" aria-hidden />
                {t}
              </li>
            ))}
          </ul>
        </div>

        <div className="card-paper p-6">
          <p className="text-sm font-medium text-ink">Exemple de recharge</p>
          <p className="meta mt-4">Choisissez votre crédit</p>
          <div role="radiogroup" aria-label="Montant de la recharge" className="mt-2 grid grid-cols-4 gap-1 rounded-[8px] border border-hairline p-1">
            {p.packs.map((x) => (
              <button
                key={x.id}
                type="button"
                role="radio"
                aria-checked={x.id === pack?.id}
                onClick={() => setPackId(x.id)}
                className={cn(
                  "rounded-[5px] py-2 text-sm transition-colors",
                  x.id === pack?.id ? "bg-brand-surface-strong font-medium text-ink" : "text-ink-muted hover:text-ink",
                )}
              >
                {euros(x.price_eur)}
              </button>
            ))}
          </div>
          {pack ? (
            <dl className="mt-5 text-sm">
              {[
                ["Recharge", euros(pack.price_eur, 2), null],
                ["Crédits", integer(base), `${euros(p.credit_value_eur, 2)} le crédit`],
                ["Bonus", bonus > 0 ? `+${integer(bonus)}` : "—", bonus > 0 ? `+${Math.round((bonus / base) * 100)} %` : null],
              ].map(([k, v, hint]) => (
                <div key={k} className="flex items-baseline justify-between border-t border-hairline py-3.5">
                  <dt className="text-ink-muted">
                    {k}
                    {hint ? <span className="meta block">{hint}</span> : null}
                  </dt>
                  <dd className="tabular-nums text-ink">{v}</dd>
                </div>
              ))}
              <div className="flex items-baseline justify-between border-y border-hairline py-3.5">
                <dt className="font-medium text-ink">Total</dt>
                <dd className="font-medium tabular-nums text-ink">{credits(pack.credits)}</dd>
              </div>
            </dl>
          ) : null}
          {pack ? (
            <p className="meta mt-4 leading-relaxed">
              Soit ≈ {integer(pack.credits / p.question_credits)} questions, ou ≈ {integer(pack.credits / p.page_credits)} pages
              indexées. Prix TTC, crédits sans expiration.
            </p>
          ) : null}
        </div>
      </div>

      <div className="mt-20">
        <h3 className="display-sm">Combien coûte 1 Go de documents ?</h3>
        <p className="copy mt-3">
          L'indexation se paie à la page, pas au poids. Sur les 84 rapports de FinanceBench, 165 Mo font
          12 013 pages, soit environ 14 Ko par page de texte : 1 Go de PDF texte représente donc environ 71 000 pages.
          Un document illustré ou scanné pèse bien plus lourd par page, et coûte donc moins cher au Go.
        </p>
        <div className="mt-6 overflow-x-auto rounded-[var(--radius-media)] border border-hairline">
          <table className="w-full min-w-[36rem] text-left text-sm">
            <thead className="bg-paper-2">
              <tr>
                <th scope="col" className="px-5 py-3.5 font-medium text-ink">1 Go de…</th>
                <th scope="col" className="px-5 py-3.5 font-medium text-ink">Poids par page</th>
                <th scope="col" className="px-5 py-3.5 font-medium text-ink">Pages</th>
                <th scope="col" className="px-5 py-3.5 text-right font-medium text-ink">Indexation</th>
              </tr>
            </thead>
            <tbody>
              {GB_PROFILES.map((g) => {
                const pages = Math.round(1_000_000 / g.kbPerPage / 1000) * 1000;
                return (
                  <tr key={g.kind} className="border-t border-hairline">
                    <th scope="row" className="px-5 py-3.5 font-normal">
                      <span className="text-ink">{g.kind}</span>
                      <span className="meta block">{g.example}</span>
                    </th>
                    <td className="px-5 py-3.5 tabular-nums text-ink-muted">≈ {g.kbPerPage} Ko</td>
                    <td className="px-5 py-3.5 tabular-nums text-ink">≈ {integer(pages)}</td>
                    <td className="px-5 py-3.5 text-right tabular-nums">
                      <span className="font-medium text-ink">≈ {euros(pages * p.page_credits * p.credit_value_eur)}</span>
                      <span className="meta block">{credits(pages * p.page_credits)}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="meta mt-4 max-w-3xl leading-relaxed">
          Indexation payée une seule fois ; ensuite, chaque question coûte {credits(p.question_credits)} ({euros(questionEur, 2)}),
          quel que soit le volume indexé. Au-delà de {integer(p.paid.pages)} pages, parlons-en :{" "}
          <Link to="/a-propos#contact" className="text-brand-deep hover:underline">offre Équipe sur devis</Link>.
        </p>
      </div>
    </Section>
  );
}
