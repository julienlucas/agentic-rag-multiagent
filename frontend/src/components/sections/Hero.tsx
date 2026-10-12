import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Container, Eyebrow } from "@/components/site/primitives";
import { PriceChips } from "@/components/site/PriceChips";
import { Button } from "@/components/ui/button";
import { usePricing, useSession } from "@/lib/session";
import { DemoChat } from "@/components/rag/DemoChat";
import { Badge } from "@/components/ui/badge";

const tooling = [
  "Reactjs",
  "LangGraph",
  "LangChain",
  "Qdrant",
  "BM25 + Vecteurs",
  "Django",
  "Amazon Bedrock",
  "Claude et Cohere",
];

export function Hero() {
  const pricing = usePricing();
  const { status } = useSession();
  return (
    <section id="top" className="border-b border-hairline bg-paper">
      <Container width="full" className="py-10 sm:py-16">
        {/* Centré, plus étroit que la nav. */}
        <div className="mx-auto max-w-5xl">
          <div className="min-w-0 text-center">
            {/* Le complément est une seconde ligne de titre : initiale minuscule et
                  teinte adoucie, pour qu'il se lise comme la suite de la phrase et non
                  comme un titre concurrent. */}
            <h1 className="display-xl">
              Agentic <span className="accent-italic">Search</span>
              <span className="display-xs mx-auto mt-4 mb-6 block max-w-3xl text-ink">
                <strong>Discutez avec vos documents</strong>, RAG agentique à 88 % de réponses
                correctes, évalué sur FinanceBench (84 rapports, 12 000 pages indexées ensemble, 135 questions)
              </span>
            </h1>

            <div className="flex flex-wrap items-center justify-center gap-3">
              {status === "authenticated" ? (
                <Button asChild variant="brand" size="lg">
                  <Link to="/app/chat">
                    Ouvrir l'app <ArrowRight />
                  </Link>
                </Button>
              ) : (
                <Button asChild variant="brand" size="lg" className="whitespace-normal text-center">
                  <Link to="/inscription">
                    Commencer gratuitement — {pricing.free.documents} documents <ArrowRight />
                  </Link>
                </Button>
              )}
              <Button asChild variant="outline" size="lg">
                <a href="#demo">Essayer la démo</a>
              </Button>
            </div>
            <PriceChips className="mt-6" />
          </div>

          <div
            id="demo"
            className="scroll-mt-20 rounded-[var(--radius-media)] border-none border-hairline"
          >
            <DemoChat />
          </div>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-x-4 gap-y-3">
            <Eyebrow>Construit avec</Eyebrow>
            <ul className="flex flex-wrap items-center justify-center gap-1.5">
              {tooling.map((t) => (
                <li key={t}>
                  <Badge variant="outlineBrand">{t}</Badge>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Container>
    </section>
  );
}
