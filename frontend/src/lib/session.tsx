import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { appApi, ApiError, FALLBACK_PRICING, type Me, type Pricing } from "@/api";
import { auth } from "@/lib/auth";

type SessionState = {
  status: "loading" | "authenticated" | "anonymous";
  me: Me | null;
  /** Solde de crédits courant (mis à jour après chaque action payante, sans recharger /api/me). */
  balance: number;
  refresh: () => Promise<Me | null>;
  setBalance: (balance: number) => void;
  logout: () => Promise<void>;
};

const SessionContext = createContext<SessionState | null>(null);

/** Session de l'utilisateur, lue sur GET /api/me (qui pose aussi le cookie CSRF). */
export function SessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<SessionState["status"]>("loading");
  const [me, setMe] = useState<Me | null>(null);

  const refresh = useCallback(async () => {
    try {
      const next = await appApi.me();
      setMe(next);
      setStatus("authenticated");
      return next;
    } catch (err) {
      if (!(err instanceof ApiError) || err.status !== 401) console.warn("GET /api/me", err);
      setMe(null);
      setStatus("anonymous");
      return null;
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const setBalance = useCallback((balance: number) => {
    setMe((m) => (m ? { ...m, workspace: { ...m.workspace, balance } } : m));
  }, []);

  const logout = useCallback(async () => {
    await auth.logout().catch(() => undefined);
    setMe(null);
    setStatus("anonymous");
  }, []);

  const value = useMemo(
    () => ({ status, me, balance: me?.workspace.balance ?? 0, refresh, setBalance, logout }),
    [status, me, refresh, setBalance, logout],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession hors de <SessionProvider>");
  return ctx;
}

/* ---------- Tarifs : une seule lecture par chargement de page ---------- */

let pricingPromise: Promise<Pricing> | null = null;

export function usePricing(): Pricing {
  const [pricing, setPricing] = useState<Pricing>(FALLBACK_PRICING);
  useEffect(() => {
    pricingPromise ??= appApi.pricing().catch(() => FALLBACK_PRICING);
    let alive = true;
    pricingPromise.then((p) => alive && setPricing(p));
    return () => {
      alive = false;
    };
  }, []);
  return pricing;
}

/* ---------- Formats ---------- */

export const euros = (n: number, digits = n % 1 === 0 ? 0 : 2) =>
  new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n);

export const integer = (n: number) => new Intl.NumberFormat("fr-FR").format(Math.round(n));

export const credits = (n: number) => `${integer(n)} crédit${Math.abs(n) >= 2 ? "s" : ""}`;
