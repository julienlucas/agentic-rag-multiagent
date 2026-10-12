import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check, Minus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Container } from "@/components/site/primitives";
import { formatFamilies } from "@/components/sections/HowItWorks";
import { cn } from "@/lib/utils";
import { credits, euros, integer, usePricing, useSession } from "@/lib/session";

/*
 * Tarifs, sur le modèle d'agentik.cc/pricing : trois offres, ce qui est inclus, un calculateur
 * de packs, des exemples concrets, une FAQ. Chiffres lus sur GET /api/pricing (repli local).
 */

function Plan({
  name,
  price,
  priceNote,
  text,
  features,
  cta,
  highlighted,
}: {
  name: string;
  price: string;
  priceNote: string;
  text: string;
  features: string[];
  cta: ReactNode;
  highlighted?: boolean;
}) {
  return (
    <div className={cn("card-paper flex flex-col p-6", highlighted && "border-brand")}>
      <div className="flex items-center justify-between">
        <h2 className="display-sm">{name}</h2>
        {highlighted ? <span className="tag border-brand text-brand-deep">Le plus courant</span> : null}
      </div>
      <p className="mt-5">
        <span className="display-md block whitespace-nowrap">{price}</span>
        <span className="meta mt-1 block">{priceNote}</span>
      </p>
      <p className="mt-3 text-sm leading-relaxed text-ink-muted">{text}</p>
      <ul className="mt-6 space-y-2.5 border-t border-hairline pt-6 text-sm">
        {features.map((f) => (
          <li key={f} className="flex gap-2.5">
            <Check className="mt-0.5 size-4 shrink-0 text-brand-deep" aria-hidden />
            <span>{f}</span>
          </li>
        ))}
      </ul>
      <div className="mt-auto pt-8">{cta}</div>
    </div>
  );
}

export function PricingPage() {
  const p = usePricing();
  const { status } = useSession();
  const signedIn = status === "authenticated";
  const [packId, setPackId] = useState<string | null>(null);
  const pack = p.packs.find((x) => x.id === packId) ?? p.packs[1] ?? p.packs[0];
  const questionEur = p.question_credits * p.credit_value_eur;
  const pageEur = p.page_credits * p.credit_value_eur;
  const baseCredits = pack ? pack.price_eur / p.credit_value_eur : 0;
  const bonus = pack && baseCredits ? Math.round(((pack.credits - baseCredits) / baseCredits) * 100) : 0;

  const startCta = (label: string, variant: "brand" | "outline") => (
    <Button asChild variant={variant} className="w-full">
      <Link to={signedIn ? "/app/credits" : "/inscription"}>
        {signedIn ? "Ouvrir mes crédits" : label} <ArrowRight />
      </Link>
    </Button>
  );

  const included: [string, string | boolean, string | boolean, string | boolean][] = [
    ["Documents", `${p.free.documents}`, `${integer(p.paid.documents)}`, "Sur mesure"],
    ["Pages indexées", `${integer(p.free.pages)} au total`, `${integer(p.paid.pages)} au total`, "Sur mesure"],
    ["Indexation", "Offerte", `${credits(p.page_credits)} par page`, `${credits(p.page_credits)} par page`],
    ["Questions", `${integer(p.free.welcome_credits)} crédits offerts`, `${credits(p.question_credits)} par question`, `${credits(p.question_credits)} par question`],
    ["Tous les formats", true, true, true],
    ["Citations ouvertes dans le document", true, true, true],
    ["Historique des conversations", true, true, true],
    ["Relevé de chaque opération", true, true, true],
    ["Facture mensuelle", false, false, true],
    ["Paiement", "Sans carte", "Carte, packs prépayés", "Virement"],
  ];

  const examples = [
    {
      title: "Un rapport annuel de 120 pages",
      value: euros(120 * pageEur),
      text: `${credits(120 * p.page_credits)} pour l'indexer une fois ; il reste interrogeable sans frais de stockage.`,
    },
    {
      title: "Une question, réponse citée",
      value: euros(questionEur),
      text: "Recherche, lecture des pages utiles par l'agent, réponse avec ses citations.",
    },
    {
      title: `Un pack de ${euros(p.packs[0]?.price_eur ?? 10)}`,
      value: `${integer((p.packs[0]?.credits ?? 1000) / p.question_credits)} questions`,
      text: `Ou ${integer((p.packs[0]?.credits ?? 1000) / p.page_credits)} pages indexées, ou un mélange des deux.`,
    },
  ];

  const faq = [
    {
      q: "Les crédits expirent-ils ?",
      a: "Non. Les crédits achetés restent sur votre compte tant qu'il existe, sans abonnement ni renouvellement automatique.",
    },
    {
      q: "Comment connaître le prix avant d'agir ?",
      a: `Le prix est affiché avant chaque action : avant d'indexer, le nombre de pages et les crédits correspondants ; une question coûte toujours ${credits(p.question_credits)}. Votre solde est visible en permanence dans l'app.`,
    },
    {
      q: "Quels formats sont acceptés ?",
      a: `${formatFamilies(p.formats).map(([family, exts]) => `${family} (${exts.join(", ")})`).join(" ; ")}. 50 Mo par fichier.`,
    },
    {
      q: "Où sont hébergées mes données ?",
      a: "Dans l'Union européenne : fichiers, index et modèles. Chaque compte a son espace isolé ; supprimer un document ou le compte efface les fichiers et leur index.",
    },
    {
      q: "Et si une indexation ou une question échoue ?",
      a: "Les crédits sont réservés au lancement puis rendus automatiquement en cas d'échec : une page qui n'a pas pu être lue, ou une question sans réponse à cause d'une erreur, ne vous coûte rien.",
    },
    {
      q: "Les prix sont-ils TTC ?",
      a: "Oui, les prix affichés en euros sont toutes taxes comprises.",
    },
  ];

  return (
    <>
      <section id="top" className="border-b border-hairline bg-paper">
        <Container className="py-14 sm:py-20">
          <span className="eyebrow">Tarifs</span>
          <h1 className="display-xl mt-4 max-w-4xl">
            Payez à l'usage. <span className="accent-italic">Commencez gratuitement.</span>
          </h1>
          <p className="copy mt-6">
            {p.free.documents} documents et {integer(p.free.welcome_credits)} crédits offerts à l'inscription, sans carte.
            Ensuite, des packs de crédits prépayés : {euros(questionEur)} la question, {euros(pageEur)} la page indexée.
          </p>
        </Container>
      </section>

      <section className="bg-paper py-[var(--section-y)]">
        <Container>
          <div className="grid gap-4 lg:grid-cols-3">
            <Plan
              name="Gratuit"
              price={euros(0)}
              priceNote="sans carte"
              text="Pour essayer sur vos propres documents."
              features={[
                `${p.free.documents} documents, ${integer(p.free.pages)} pages au total`,
                "Indexation offerte",
                `${integer(p.free.welcome_credits)} crédits offerts, soit ${integer(p.free.welcome_credits / p.question_credits)} questions`,
                "Tous les formats",
              ]}
              cta={startCta("Créer mon espace", "outline")}
            />
            <Plan
              highlighted
              name="À la carte"
              price={`dès ${euros(p.packs[0]?.price_eur ?? 10)}`}
              priceNote="packs prépayés"
              text="Vous rechargez quand vous voulez ; les crédits n'expirent pas."
              features={[
                `${integer(p.paid.documents)} documents, ${integer(p.paid.pages)} pages au total`,
                `${credits(p.question_credits)} par question (${euros(questionEur)})`,
                `${credits(p.page_credits)} par page indexée (${euros(pageEur)})`,
                "Jusqu'à 10 % de crédits en plus sur les gros packs",
              ]}
              cta={startCta("Commencer", "brand")}
            />
            <Plan
              name="Équipe"
              price="Sur devis"
              priceNote="facture mensuelle"
              text="Gros volumes, plusieurs utilisateurs, besoins de conformité."
              features={[
                "Volumes de documents sur mesure",
                "Mêmes prix à l'usage, facturés au mois",
                "Accompagnement à la mise en place",
              ]}
              cta={
                <Button asChild variant="outline" className="w-full">
                  <Link to="/a-propos#contact">Nous contacter</Link>
                </Button>
              }
            />
          </div>
        </Container>
      </section>

      <section className="border-t border-hairline bg-paper py-[var(--section-y)]">
        <Container>
          <span className="eyebrow">Ce qui est inclus</span>
          <div className="mt-6 overflow-x-auto">
            <table className="w-full min-w-[40rem] border-collapse text-sm">
              <thead>
                <tr className="text-left">
                  <th scope="col" className="mono-xs uppercase tracking-[0.09em] text-ink-faint w-[34%] pb-3 font-normal">Fonction</th>
                  <th scope="col" className="mono-xs uppercase tracking-[0.09em] text-ink-faint pb-3 font-normal">Gratuit</th>
                  <th scope="col" className="mono-xs uppercase tracking-[0.09em] text-ink-faint pb-3 font-normal">À la carte</th>
                  <th scope="col" className="mono-xs uppercase tracking-[0.09em] text-ink-faint pb-3 font-normal">Équipe</th>
                </tr>
              </thead>
              <tbody>
                {included.map(([label, ...cells]) => (
                  <tr key={label} className="border-t border-hairline">
                    <th scope="row" className="py-3.5 pr-4 text-left font-medium text-ink">
                      {label}
                    </th>
                    {cells.map((c, i) => (
                      <td key={i} className="py-3.5 pr-4 text-ink-muted">
                        {c === true ? (
                          <Check className="size-4 text-brand-deep" aria-label="Inclus" />
                        ) : c === false ? (
                          <Minus className="size-4 text-ink-faint" aria-label="Non inclus" />
                        ) : (
                          c
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Container>
      </section>

      <section className="border-t border-hairline bg-paper-2 py-[var(--section-y)]">
        <Container>
          <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <div>
              <span className="eyebrow">Calculateur</span>
              <h2 className="display-md mt-4">Choisissez votre pack</h2>
              <p className="copy mt-4 text-sm">
                Les crédits servent indifféremment aux questions et à l'indexation. Ils s'ajoutent à votre solde ;
                le paiement par carte se fait sur Stripe.
              </p>
              <div role="radiogroup" aria-label="Montant du pack" className="mt-6 grid grid-cols-2 gap-2 sm:grid-cols-4">
                {p.packs.map((x) => (
                  <button
                    key={x.id}
                    type="button"
                    role="radio"
                    aria-checked={x.id === pack?.id}
                    onClick={() => setPackId(x.id)}
                    className={cn(
                      "mono-xs cursor-pointer rounded-sm border px-3 py-3 text-sm transition-colors",
                      x.id === pack?.id
                        ? "border-brand bg-brand text-on-brand"
                        : "border-hairline-strong bg-paper text-ink hover:border-brand",
                    )}
                  >
                    {euros(x.price_eur)}
                  </button>
                ))}
              </div>
            </div>
            {pack ? (
              <div className="card-paper p-6">
                <dl className="divide-y divide-hairline text-sm">
                  {[
                    ["Crédits", integer(pack.credits), bonus > 0 ? `+${bonus} % offerts` : null],
                    ["Soit des questions", integer(pack.credits / p.question_credits), null],
                    ["Ou des pages indexées", integer(pack.credits / p.page_credits), null],
                    ["Prix d'une question", euros((pack.price_eur / pack.credits) * p.question_credits, 2), null],
                  ].map(([label, value, note]) => (
                    <div key={label as string} className="flex items-baseline justify-between gap-4 py-3">
                      <dt className="text-ink-muted">{label}</dt>
                      <dd className="text-right">
                        <span className="mono-xs text-base text-ink">{value}</span>
                        {note ? <span className="mono-xs ml-2 text-brand-deep">{note}</span> : null}
                      </dd>
                    </div>
                  ))}
                  <div className="flex items-baseline justify-between gap-4 pt-4">
                    <dt className="font-medium text-ink">Total TTC</dt>
                    <dd className="display-sm">{euros(pack.price_eur)}</dd>
                  </div>
                </dl>
                <Button asChild variant="brand" className="mt-6 w-full">
                  <Link to={signedIn ? "/app/credits" : "/inscription"}>
                    {signedIn ? "Acheter ce pack" : "Créer un compte pour acheter"} <ArrowRight />
                  </Link>
                </Button>
              </div>
            ) : null}
          </div>
        </Container>
      </section>

      <section className="border-t border-hairline bg-paper py-[var(--section-y)]">
        <Container>
          <span className="eyebrow">Ce que quelques euros achètent</span>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {examples.map((e) => (
              <div key={e.title} className="card-paper p-6">
                <p className="text-sm font-medium text-ink">{e.title}</p>
                <p className="display-md mt-3 text-brand-deep">{e.value}</p>
                <p className="mt-3 text-sm leading-relaxed text-ink-muted">{e.text}</p>
              </div>
            ))}
          </div>
        </Container>
      </section>

      <section className="border-t border-hairline bg-paper py-[var(--section-y)]">
        <Container width="narrow">
          <span className="eyebrow">Questions</span>
          <div className="mt-6 divide-y divide-hairline border-y border-hairline">
            {faq.map((f) => (
              <details key={f.q} className="group py-4">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium text-ink [&::-webkit-details-marker]:hidden">
                  {f.q}
                  <span aria-hidden className="mono-xs text-brand-deep transition-transform group-open:rotate-45">
                    +
                  </span>
                </summary>
                <p className="copy mt-3 text-sm">{f.a}</p>
              </details>
            ))}
          </div>
        </Container>
      </section>
    </>
  );
}
