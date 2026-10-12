import { Link } from "react-router-dom";
import { ArrowUp, ArrowUpRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Container } from "@/components/site/primitives";
import { LINKEDIN } from "@/components/site/links";
import { scrollToHash } from "@/lib/use-lenis";

type FooterLink = { href: string; label: string; external?: boolean };

const columns: { title: string; links: FooterLink[] }[] = [
  {
    title: "Explorer",
    links: [
      { href: "/#demo", label: "Démo" },
      { href: "/#fonctionnement", label: "Fonctionnement" },
      { href: "/#agents", label: "Les agents" },
      { href: "/#resultats", label: "Résultats" },
      { href: "/#outils", label: "Les outils" },
      { href: "/tarifs", label: "Tarifs" },
    ],
  },
  {
    title: "Ressources",
    links: [
      { href: "https://github.com/julienlucas/agentic-rag-with-tools", label: "Code sur GitHub", external: true },
      { href: "https://github.com/patronus-ai/financebench", label: "FinanceBench", external: true },
    ],
  },
  {
    title: "À propos",
    links: [
      { href: "/a-propos", label: "À propos" },
      { href: "/a-propos#contact", label: "Contact" },
      { href: LINKEDIN, label: "LinkedIn", external: true },
    ],
  },
];

/*
 * Pied de page : une phrase d'accroche et ses deux actions, les colonnes de liens, puis une
 * barre basse (copyright, retour en haut). Sur fond papier, séparé du contenu par un filet.
 */
export function Footer() {
  return (
    <footer className="border-t border-hairline bg-paper">
      <Container width="full" className="py-[var(--section-y)]">
        <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <p className="display-lg font-semibold">
              Vos documents deviennent des <span className="accent-italic">réponses sourcées</span>.
            </p>
            <p className="copy mt-4">
              Un agent qui lit, cherche et cite la page exacte de vos documents.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button asChild variant="brand">
              <Link to="/inscription">Commencer gratuitement</Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/#demo">Essayer la démo</Link>
            </Button>
            <Button asChild variant="outline">
              <a href={LINKEDIN} target="_blank" rel="noreferrer">
                Me contacter <ArrowUpRight />
              </a>
            </Button>
          </div>
        </div>

        <div className="mt-16 grid gap-10 border-t border-hairline pt-10 sm:grid-cols-2 lg:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div>
            <Link to="/" className="text-[1.375rem] font-semibold tracking-[-0.035em] text-ink">
              Agentic <span className="accent-italic">Search</span>
            </Link>
            <p className="mt-3 max-w-xs text-sm leading-relaxed text-ink-muted">
              RAG agentique à outils de navigation dans les documents, évalué sur FinanceBench.
            </p>
          </div>
          {columns.map((col) => (
            <nav key={col.title} aria-label={col.title}>
              <span className="text-sm font-medium text-ink">{col.title}</span>
              <ul className="mt-4 space-y-2.5">
                {col.links.map((l) => (
                  <li key={l.href}>
                    {l.external ? (
                      <a href={l.href} target="_blank" rel="noreferrer" className="nav-link text-sm">
                        {l.label}
                        <span className="text-brand"> ↗</span>
                      </a>
                    ) : (
                      <Link to={l.href} className="nav-link text-sm">
                        {l.label}
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="mt-14 flex flex-wrap items-center justify-between gap-4 border-t border-hairline pt-6 text-sm text-ink-faint">
          <span>© {new Date().getFullYear()} Julien Lucas · Agentic Search</span>
          <button
            type="button"
            onClick={() => scrollToHash("#top")}
            className="nav-link inline-flex items-center gap-1.5"
          >
            Retour en haut <ArrowUp className="size-3.5" />
          </button>
        </div>
      </Container>
    </footer>
  );
}
