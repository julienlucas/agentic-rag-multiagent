import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ArrowRight, CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { appApi, ApiError, type CreditEntry } from "@/api";
import { errorMessage } from "@/lib/http";
import { euros, integer, usePricing, useSession } from "@/lib/session";
import { cn } from "@/lib/utils";
import { PageHeader } from "./AppLayout";

const REASONS: Record<CreditEntry["reason"], string> = {
  welcome: "Bienvenue",
  purchase: "Achat",
  question: "Question",
  indexing: "Indexation",
  refund: "Remboursement",
};

const formatDate = (iso: string) =>
  new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(
    new Date(iso),
  );

export function CreditsPage() {
  const pricing = usePricing();
  const { balance, setBalance, refresh } = useSession();
  const [params, setParams] = useSearchParams();
  const paid = params.get("paid") === "1";
  const [entries, setEntries] = useState<CreditEntry[] | null>(null);
  const [buying, setBuying] = useState<string | null>(null);
  const [billing, setBilling] = useState(true);

  useEffect(() => {
    appApi
      .credits()
      .then((r) => {
        setEntries(r.entries);
        setBalance(r.balance);
        setBilling(r.billing_enabled !== false);
      })
      .catch((err) => {
        setEntries([]);
        toast.error("Relevé indisponible", { description: errorMessage(err) });
      });
    // Retour de Stripe : le webhook a pu créditer le compte entre-temps.
    if (paid) refresh();
  }, [paid, refresh, setBalance]);

  async function buy(packId: string) {
    setBuying(packId);
    try {
      const { url } = await appApi.checkout(packId);
      window.location.assign(url);
    } catch (err) {
      setBuying(null);
      const unavailable = err instanceof ApiError && err.status === 503;
      toast.error(unavailable ? "Paiement indisponible pour le moment" : "Paiement impossible", {
        description: unavailable ? "Réessayez plus tard ou contactez-nous." : errorMessage(err),
      });
    }
  }

  return (
    <div className="h-full overflow-y-auto" data-lenis-prevent>
      <div className="mx-auto max-w-6xl space-y-8 px-4 py-8 sm:px-8">
        <PageHeader eyebrow="Espace" title="Crédits" />

        {paid ? (
          <div role="status" className="flex items-start gap-3 rounded-[var(--radius-media)] border border-success/30 bg-success/10 p-4 text-sm">
            <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" />
            <div className="min-w-0 flex-1">
              <p className="font-medium text-ink">Paiement reçu, merci !</p>
              <p className="text-ink-muted">Vos crédits sont ajoutés à votre solde (cela peut prendre quelques secondes).</p>
            </div>
            <button type="button" onClick={() => setParams({})} className="mono-xs cursor-pointer text-ink-muted hover:text-ink">
              fermer
            </button>
          </div>
        ) : null}

        <div className="grid gap-4 lg:grid-cols-[18rem_minmax(0,1fr)]">
          <div className="card-paper p-6">
            <span className="eyebrow">Solde</span>
            <p className="mt-2 flex items-baseline gap-2">
              <span className="display-lg tabular-nums">{integer(balance)}</span>
              <span className="meta">crédits</span>
            </p>
            <dl className="mt-5 space-y-2 border-t border-hairline pt-4 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-ink-muted">Questions</dt>
                <dd className="mono-xs text-ink">≈ {integer(Math.floor(balance / pricing.question_credits))}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-ink-muted">Ou pages indexées</dt>
                <dd className="mono-xs text-ink">≈ {integer(Math.floor(balance / pricing.page_credits))}</dd>
              </div>
            </dl>
          </div>

          <div>
            <span className="eyebrow">Recharger</span>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {pricing.packs.map((p) => {
                const base = p.price_eur / pricing.credit_value_eur;
                const bonus = Math.round(((p.credits - base) / base) * 100);
                return (
                  <div key={p.id} className="card-paper flex flex-col p-5">
                    <p className="display-md">{euros(p.price_eur)}</p>
                    <p className="mono-xs mt-2 text-ink">{integer(p.credits)} crédits</p>
                    <p className="meta mt-1">
                      ≈ {integer(p.credits / pricing.question_credits)} questions
                      {bonus > 0 ? <span className="text-brand-deep"> · +{bonus} %</span> : null}
                    </p>
                    <Button
                      variant={p.id === pricing.packs[1]?.id ? "brand" : "outline"}
                      size="sm"
                      className="mt-5"
                      disabled={buying !== null || !billing}
                      onClick={() => buy(p.id)}
                    >
                      {!billing ? (
                        "Bientôt disponible"
                      ) : buying === p.id ? (
                        <>
                          <Loader2 className="animate-spin" /> Redirection…
                        </>
                      ) : (
                        <>
                          Acheter <ArrowRight />
                        </>
                      )}
                    </Button>
                  </div>
                );
              })}
            </div>
            <p className="meta mt-3">
              {billing
                ? "Prix TTC · paiement sécurisé par Stripe · crédits sans expiration"
                : "Paiement bientôt disponible. Prix TTC · crédits sans expiration"}
            </p>
          </div>
        </div>

        <section aria-label="Relevé des opérations">
          <span className="eyebrow">Relevé</span>
          <div className="card-paper mt-3 overflow-x-auto">
            {entries === null ? (
              <p className="meta inline-flex items-center gap-2 p-4">
                <Loader2 className="size-3.5 animate-spin" /> chargement…
              </p>
            ) : entries.length === 0 ? (
              <p className="p-6 text-sm text-ink-muted">Aucune opération pour l'instant.</p>
            ) : (
              <table className="w-full min-w-[32rem] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-hairline text-left">
                    <th scope="col" className="mono-xs uppercase tracking-[0.09em] text-ink-faint px-4 py-3 font-normal">Date</th>
                    <th scope="col" className="mono-xs uppercase tracking-[0.09em] text-ink-faint px-4 py-3 font-normal">Opération</th>
                    <th scope="col" className="mono-xs uppercase tracking-[0.09em] text-ink-faint px-4 py-3 text-right font-normal">Crédits</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((e) => (
                    <tr key={e.id} className="border-b border-hairline last:border-0">
                      <td className="mono-xs whitespace-nowrap px-4 py-3 text-ink-muted">{formatDate(e.created_at)}</td>
                      <td className="px-4 py-3">
                        <span className="tag mr-2 normal-case">{REASONS[e.reason] ?? e.reason}</span>
                        <span className="text-ink">{e.label}</span>
                      </td>
                      <td className={cn("mono-xs px-4 py-3 text-right", e.delta > 0 ? "text-success" : "text-ink")}>
                        {e.delta > 0 ? "+" : "−"}
                        {integer(Math.abs(e.delta))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
