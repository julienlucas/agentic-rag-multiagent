import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { ContactWidget } from "@/components/site/ContactWidget";
import { Footer } from "@/components/site/Footer";
import { Navbar } from "@/components/site/Navbar";
import { scrollToHash, useLenis } from "@/lib/use-lenis";

/**
 * Pages publiques (accueil, tarifs, à propos) : barre de navigation, pied de page, défilement
 * inertiel. À chaque changement de page : en haut, ou sur l'ancre demandée.
 */
export function SiteLayout({ footer = true }: { footer?: boolean }) {
  useLenis();
  const { pathname, hash } = useLocation();

  useEffect(() => {
    if (hash.length > 1) {
      requestAnimationFrame(() => requestAnimationFrame(() => scrollToHash(hash)));
    } else {
      window.scrollTo(0, 0);
    }
  }, [pathname, hash]);

  return (
    <>
      <Navbar />
      <main>
        <Outlet />
      </main>
      {footer ? <Footer /> : null}
      {footer ? <ContactWidget /> : null}
    </>
  );
}
