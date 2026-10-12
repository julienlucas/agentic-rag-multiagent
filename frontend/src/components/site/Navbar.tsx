import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Container } from "@/components/site/primitives";
import { GITHUB_REPO } from "@/components/site/links";
import { useSession } from "@/lib/session";

const links = [
  { href: "/tarifs", label: "Tarifs" },
  { href: "/#resultats", label: "Résultats" },
  { href: GITHUB_REPO, label: "GitHub", external: true },
];

function NavItem({ href, label, external, className, onClick }: (typeof links)[number] & { className?: string; onClick?: () => void }) {
  if (external) {
    return (
      <a href={href} target="_blank" rel="noreferrer" className={className} onClick={onClick}>
        {label}
        <span className="text-brand"> ↗</span>
      </a>
    );
  }
  return (
    <Link to={href} className={className} onClick={onClick}>
      {label}
    </Link>
  );
}

/*
 * Barre de navigation collante : fond papier légèrement translucide, filet en pied de barre.
 * À droite, l'accès au compte : « Connexion » + « Commencer gratuitement », ou « Ouvrir l'app ».
 * Sous `md`, les liens passent dans un panneau déroulant.
 */
export function Navbar() {
  const [open, setOpen] = useState(false);
  const { status } = useSession();
  const signedIn = status === "authenticated";
  const close = () => setOpen(false);

  const account = (mobile: boolean) =>
    signedIn ? (
      <Button asChild size="sm" variant="brand" className={mobile ? "self-start" : undefined}>
        <Link to="/app/chat" onClick={close}>
          Ouvrir l'app <ArrowRight />
        </Link>
      </Button>
    ) : (
      <>
        <Link to="/connexion" onClick={close} className={cn("nav-link font-sans text-sm font-medium", mobile && "py-3")}>
          Connexion
        </Link>
        <Button asChild size="sm" variant="brand" className={mobile ? "self-start" : undefined}>
          <Link to="/inscription" onClick={close}>
            Commencer gratuitement
          </Link>
        </Button>
      </>
    );

  return (
    <header
      className={cn(
        "sticky top-0 z-40 border-b bg-paper/90 backdrop-blur supports-[backdrop-filter]:bg-paper/75",
        "transition-[border-color] duration-[var(--dur-fast)]",
        "border-hairline",
      )}
    >
      <Container width="full" className="flex h-14 items-center justify-between gap-6">
        <Link to="/" className="text-[1.6275rem] font-semibold tracking-[-0.035em] text-ink" onClick={close}>
          Agentic <span className="accent-italic">Search</span>
        </Link>

        <nav aria-label="Navigation principale" className="hidden items-center gap-7 md:flex">
          {links.map((l) => (
            <NavItem key={l.href} {...l} className="nav-link font-sans text-sm font-medium" />
          ))}
          <span aria-hidden className="h-5 w-px bg-hairline" />
          {account(false)}
        </nav>

        <button
          type="button"
          className="inline-flex size-9 items-center justify-center rounded-sm text-ink md:hidden"
          aria-label={open ? "Fermer le menu" : "Ouvrir le menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </Container>

      {open ? (
        <nav aria-label="Navigation principale" className="border-t border-hairline md:hidden">
          <Container width="full" className="flex flex-col py-2">
            {links.map((l) => (
              <NavItem key={l.href} {...l} onClick={close} className="nav-link font-sans py-3 text-sm font-medium" />
            ))}
            <div className="my-2 flex flex-col gap-1 border-t border-hairline pt-2">{account(true)}</div>
          </Container>
        </nav>
      ) : null}
    </header>
  );
}
