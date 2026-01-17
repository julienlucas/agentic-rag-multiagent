import { useState } from "react";
import Index from "@/index";
import { Button } from "@/components/ui/button";
import { ArrowRight, Calendar, X } from "lucide-react";
import { Card, CardTitle, CardDescription } from "@/components/ui/card";

const App = () => {
  const [isContactOpen, setIsContactOpen] = useState(true);

  const scrollToContact = () => {
    const target = document.getElementById("contact-form");
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const scrollToFooter = () => {
    const target = document.getElementById("footer-projects");
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  return (
    <>
      <header className="flex justify-end items-center h-14 px-2 w-full border-b border-gray-200">
        <div className="mx-auto max-w-5xl w-full flex justify-between items-center">
          <a
            href="https://github.com/julienlucas/agentic-rag-multiagent"
            target="_blank"
          >
            <Button size="default">Repo Github</Button>
          </a>
          <button
            type="button"
            onClick={scrollToFooter}
            className="text-sm flex items-center gap-1 underline hover:no-underline"
          >
            Consultez mes autres projets IA
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </header>
      <Index />
      <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
        {isContactOpen && (
          <div
            className="relative w-[260px] cursor-pointer rounded-xl border border-zinc-200 bg-white shadow-lg p-3 text-sm text-zinc-800"
            onClick={scrollToContact}
            role="button"
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                scrollToContact();
              }
            }}
          >
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                setIsContactOpen(false);
              }}
              className="absolute right-2 top-2 text-zinc-500 hover:text-zinc-800"
              aria-label="Fermer"
            >
              <X className="h-4 w-4" />
            </button>
            <img
              src="/static/julienlucas.jpg"
              alt="Contact"
              className="w-8 h-8 rounded-full"
            />
            <p className="text-lg font-bold text-black leading-6 mt-1">
              Call projet IA
            </p>
            <p className="text-sm leading-5">
              20 minutes pour valider votre projet d'automatisation ou
              d'application. N'hésitez pas à me contacter.
            </p>
            <Button
              size="sm"
              className="mt-3 w-full"
              onClick={(event) => {
                event.stopPropagation();
                scrollToContact();
              }}
            >
              <Calendar className="h-4 w-4" />
              Prendre contact
            </Button>
          </div>
        )}
        <button
          type="button"
          onClick={() => setIsContactOpen((current) => !current)}
          className="relative h-12 w-12 rounded-full bg-black text-white flex items-center justify-center shadow-lg hover:bg-black/80"
          aria-label="Contacter Julien"
        >
          <span
            className="absolute inset-0.5 rounded-full animate-spin"
            style={{
              animationDuration: "3s",
              filter: "blur(7px)",
              willChange: "transform",
              background:
                "conic-gradient(from 0deg, rgba(255,255,255,0) 0deg, rgba(255,255,255,0.2) 120deg, rgba(255,255,255,0.9) 220deg, rgba(255,255,255,0) 360deg)",
              WebkitMask:
                "radial-gradient(farthest-side, transparent calc(100% - 2px), #000 0)",
              mask: "radial-gradient(farthest-side, transparent calc(100% - 2px), #000 0)",
            }}
          />
          ✉️
        </button>
      </div>
      <footer id="footer-projects" className="w-full border-t border-zinc-200 pt-4">
        <Card className="border-none mx-auto max-w-2xl w-full">
          <CardTitle variant="h4">Mes autres projets IA</CardTitle>
          <CardDescription className="text-sm flex items-center gap-1">
            <a
              href="https://fakefinder-nanobananapro.up.railway.app"
              target="_blank"
              rel="noreferrer"
              className="hover:underline"
            >
              Fakefinder Nano Banana Pro
            </a>
          </CardDescription>
          <CardDescription className="text-sm flex items-center gap-1">
            <a
              href="https://mm-rag-styleanalyzer.up.railway.app"
              target="_blank"
              rel="noreferrer"
              className="hover:underline"
            >
              StyleAnalyzer - Analyse vètement, style et MM-RAG recommandation
            </a>
          </CardDescription>
          <CardDescription className="text-sm flex items-center gap-1">
            <a
              href="https://pneumodiag.up.railway.app"
              target="_blank"
              rel="noreferrer"
              className="hover:underline"
            >
              PneumoDiag - Pneumonia Diagnostic Assistant
            </a>
          </CardDescription>
          <div className="max-w-[1100px] mx-auto px-4 sm:px-6 lg:px-8 py-4 pt-8">
            <div className="text-sm flex justify-center">
              © {new Date().getFullYear()} Julien Lucas. Tous droits réservés.
            </div>
          </div>
        </Card>
      </footer>
    </>
  );
};

export default App;
