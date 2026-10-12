import { Link } from "react-router-dom";
import { ArrowUp, ArrowUpRight } from "lucide-react";
import { Container } from "@/components/site/primitives";
import { GITHUB_REPO, LINKEDIN } from "@/components/site/links";
import { scrollToHash } from "@/lib/use-lenis";
import { useSession } from "@/lib/session";

type FooterLink = { href: string; label: string; external?: boolean };

const columns: { title: string; links: FooterLink[] }[] = [
  {
    title: "Produit",
    links: [
      { href: "/inscription", label: "Créer mon espace" },
      { href: "/demo", label: "Démo" },
      { href: "/#evaluation", label: "Évaluation" },
      { href: "/tarifs", label: "Tarifs" },
      { href: "/app", label: "Ouvrir l'app" },
    ],
  },
  {
    title: "Ressources",
    links: [
      { href: GITHUB_REPO, label: "Code sur GitHub", external: true },
      { href: "https://github.com/patronus-ai/financebench", label: "FinanceBench", external: true },
    ],
  },
  {
    title: "Société",
    links: [
      { href: "/a-propos", label: "À propos" },
      { href: "/a-propos#contact", label: "Contact" },
      { href: "/securite", label: "Sécurité" },
      { href: LINKEDIN, label: "LinkedIn", external: true },
    ],
  },
  {
    title: "Légal",
    links: [
      { href: "/conditions", label: "Conditions d'utilisation" },
      { href: "/confidentialite", label: "Confidentialité" },
      { href: "/mentions-legales", label: "Mentions légales" },
    ],
  },
];

function FooterAnchor({ link }: { link: FooterLink }) {
  const cls = "inline-flex items-center gap-1 text-[0.9375rem] font-medium text-ink underline-offset-4 decoration-1 hover:underline";
  if (link.external) {
    return (
      <a href={link.href} target="_blank" rel="noreferrer" className={cls}>
        {link.label}
        <ArrowUpRight className="size-3.5" aria-hidden />
      </a>
    );
  }
  return (
    <Link to={link.href} className={cls}>
      {link.label}
    </Link>
  );
}

/*
 * Pied de page orange, sur le modèle d'agentik.cc : les colonnes de liens, une barre (marque,
 * copyright, retour en haut), puis la signature en grand. Texte en encre : le blanc ne tient pas
 * sur l'orange vif.
 */
export function Footer() {
  const { status } = useSession();
  return (
    <footer className="surface-orange">
      <Container width="full" className="pt-16 sm:pt-20">
        <nav aria-label="Pied de page" className="grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-4">
          {columns.map((col) => (
            <div key={col.title}>
              <p className="text-sm text-ink-muted">{col.title}</p>
              <ul className="mt-4 space-y-3">
                {col.links.map((l) => (
                  <li key={l.label}>
                    <FooterAnchor link={l} />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        <div className="mt-16 flex flex-col gap-4 border-t border-hairline pt-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-baseline gap-4">
            <Link to="/" className="text-2xl font-semibold tracking-[-0.035em] text-ink">
              Agentic <span className="font-serif italic font-normal">Search</span>
            </Link>
            <span className="text-sm text-ink-muted">© {new Date().getFullYear()}</span>
          </div>
          <button
            type="button"
            onClick={() => scrollToHash("#top")}
            className="inline-flex items-center gap-1.5 self-start text-sm font-medium text-ink hover:underline sm:self-auto"
          >
            Retour en haut <ArrowUp className="size-3.5" aria-hidden />
          </button>
        </div>

        <div className="py-24 text-center sm:py-32">
          <p className="mx-auto max-w-5xl font-display text-[clamp(2.5rem,1.5rem+4.5vw,5.25rem)] leading-[0.98] font-semibold tracking-[-0.045em] text-ink">
            Vos documents ont la réponse.
            <span className="block font-serif font-normal italic tracking-[-0.02em] text-orange-900">
              L'agent va la chercher.
            </span>
          </p>
          <p className="mx-auto mt-6 max-w-xl text-ink-muted">
            Il lit, cherche et cite la page exacte. 88 % de réponses correctes sur FinanceBench.
          </p>
          <Link
            to={status === "authenticated" ? "/app/documents" : "/inscription"}
            className="mt-10 inline-flex items-center gap-2 rounded-sm bg-ink px-5 py-3 text-sm font-medium text-paper transition-colors hover:bg-ink-soft"
          >
            Insérez votre premier document <ArrowUpRight className="size-4" aria-hidden />
          </Link>
        </div>
      </Container>
    </footer>
  );
}
