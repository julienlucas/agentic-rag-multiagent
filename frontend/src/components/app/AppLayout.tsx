import { useEffect, useState, type ReactNode } from "react";
import { Link, Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Coins, FileText, Loader2, LogOut, Menu, MessageSquare, UserRound, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { credits, usePricing, useSession } from "@/lib/session";

const nav = [
  { to: "/app/chat", label: "Chat", icon: MessageSquare },
  { to: "/app/documents", label: "Documents", icon: FileText },
  { to: "/app/credits", label: "Crédits", icon: Coins },
  { to: "/app/compte", label: "Compte", icon: UserRound },
];

/** Les routes /app/* exigent une session : sinon, connexion puis retour à la page demandée. */
export function RequireAuth() {
  const { status } = useSession();
  const location = useLocation();
  if (status === "loading") {
    return (
      <div className="grid min-h-dvh place-items-center bg-paper-2" role="status" aria-live="polite">
        <span className="meta inline-flex items-center gap-2">
          <Loader2 className="size-4 animate-spin text-brand-deep" /> chargement de votre espace…
        </span>
      </div>
    );
  }
  if (status === "anonymous") {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/connexion?next=${encodeURIComponent(next)}`} replace />;
  }
  return <Outlet />;
}

function Logo() {
  return (
    <Link to="/" className="text-[1.375rem] font-semibold tracking-[-0.035em] text-ink">
      Agentic <span className="accent-italic">Search</span>
    </Link>
  );
}

/** Solde de crédits, toujours visible ; orange quand il ne permet plus une question. */
function Balance({ compact }: { compact?: boolean }) {
  const { balance } = useSession();
  const pricing = usePricing();
  const low = balance < pricing.question_credits;
  if (compact) {
    return (
      <Link
        to="/app/credits"
        className={cn(
          "mono-xs inline-flex items-center gap-1.5 rounded-sm border px-2 py-1",
          low ? "border-brand bg-brand-surface text-brand-deep" : "border-hairline text-ink",
        )}
        aria-label={`Solde : ${credits(balance)}`}
      >
        <Coins className="size-3.5" /> {credits(balance)}
      </Link>
    );
  }
  return (
    <div className={cn("rounded-[var(--radius-media)] border p-4", low ? "border-brand bg-brand-surface" : "border-hairline bg-paper")}>
      <span className="eyebrow">Solde</span>
      <p className="mt-1 flex items-baseline gap-1.5">
        <span className="display-sm tabular-nums">{new Intl.NumberFormat("fr-FR").format(balance)}</span>
        <span className="meta">crédits</span>
      </p>
      <p className="meta mt-1">
        {low ? "Insuffisant pour une question" : `≈ ${Math.floor(balance / pricing.question_credits)} questions`}
      </p>
      <Link to="/app/credits" className="mono-xs mt-3 inline-block text-brand-deep hover:underline">
        Recharger →
      </Link>
    </div>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { me, logout } = useSession();
  const navigate = useNavigate();
  return (
    <div className="flex h-full flex-col gap-6">
      <nav aria-label="Espace" className="flex flex-col gap-0.5">
        {nav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2.5 rounded-sm px-3 py-2 text-sm transition-colors",
                isActive ? "bg-brand-surface font-medium text-ink" : "text-ink-muted hover:bg-paper-3 hover:text-ink",
              )
            }
          >
            <Icon className="size-4 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>
      <Balance />
      <div className="mt-auto border-t border-hairline pt-4">
        <p className="truncate text-sm text-ink" title={me?.user.email}>
          {me?.user.email}
        </p>
        <p className="meta">{me?.workspace.plan === "paid" ? "à la carte" : "offre gratuite"}</p>
        <button
          type="button"
          onClick={async () => {
            await logout();
            navigate("/");
          }}
          className="mono-xs mt-3 inline-flex cursor-pointer items-center gap-1.5 text-ink-muted hover:text-ink"
        >
          <LogOut className="size-3.5" /> Se déconnecter
        </button>
      </div>
    </div>
  );
}

/**
 * Coquille de l'espace connecté : barre latérale (Chat, Documents, Crédits, Compte, solde) en
 * desktop ; barre du haut + tiroir en mobile. Le contenu occupe la hauteur de l'écran, chaque
 * page gère son propre défilement.
 */
export function AppLayout() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);

  return (
    <div className="flex min-h-dvh bg-paper-2 lg:h-dvh">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-hairline bg-paper px-4 py-5 lg:flex">
        <div className="mb-8 px-1">
          <Logo />
        </div>
        <SidebarContent />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b border-hairline bg-paper px-4 lg:hidden">
          <Logo />
          <div className="flex items-center gap-2">
            <Balance compact />
            <button
              type="button"
              aria-label={open ? "Fermer le menu" : "Ouvrir le menu"}
              aria-expanded={open}
              onClick={() => setOpen((v) => !v)}
              className="inline-grid size-9 cursor-pointer place-items-center rounded-sm text-ink"
            >
              {open ? <X className="size-5" /> : <Menu className="size-5" />}
            </button>
          </div>
        </header>
        {open ? (
          <div className="fixed inset-x-0 top-14 bottom-0 z-30 overflow-y-auto border-t border-hairline bg-paper px-4 py-5 lg:hidden">
            <SidebarContent onNavigate={() => setOpen(false)} />
          </div>
        ) : null}

        <main className="min-h-0 min-w-0 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

/** En-tête d'une page de l'espace : surtitre, titre, actions à droite. */
export function PageHeader({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1 className="display-md mt-2">{title}</h1>
      </div>
      {children}
    </div>
  );
}
