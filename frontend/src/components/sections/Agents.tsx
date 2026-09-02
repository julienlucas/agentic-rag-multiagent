import { Redo2, ShieldCheck, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Section } from "@/components/site/primitives";

const agents = [
  {
    icon: <ShieldCheck />,
    index: "A1",
    title: "Agent vérificateur de pertinence",
    model: "mistral-small",
    text: "Lit les 3 meilleurs passages rerankés et décide s'ils répondent vraiment à la question : CAN_ANSWER, PARTIAL ou NO_MATCH. C'est lui qui autorise — ou non — la génération.",
  },
  {
    icon: <Redo2 />,
    index: "A2",
    title: "Agent de recherche corrective",
    model: "mistral-small",
    text: "Si le vérificateur classe les passages PARTIAL ou NO_MATCH, il réécrit la question dans le vocabulaire du document (« legal battles » → litigation), relance la recherche et ajoute jusqu'à 5 passages — reclassés contre la question d'origine — après les 10 initiaux, sans jamais les remplacer. Un tour au plus.",
  },
  {
    icon: <Sparkles />,
    index: "A3",
    title: "Agent de recherche",
    model: "mistral-large",
    text: "Génère la réponse finale, contrainte aux 10 meilleurs passages parents. Refuse explicitement quand l'information n'y est pas, plutôt que de combler le vide.",
  },
];

export function Agents() {
  return (
    <Section
      id="agents"
      index="02"
      eyebrow="Les agents"
      title={
        <>
          Trois agents, orchestrés par <span className="accent-italic">LangGraph</span>.
        </>
      }
      intro="Le retriever remonte les passages ; les agents décident quand chercher davantage, quand répondre et quand refuser. Le grand modèle n'intervient qu'une fois, pour rédiger."
    >
      <div className="grid gap-4 md:grid-cols-3">
        {agents.map((a) => (
          <div key={a.title} className="card-paper flex h-full flex-col p-6">
            <div className="flex items-center justify-between">
              <span className="inline-flex size-9 items-center justify-center rounded-md bg-brand-surface text-brand-deep [&_svg]:size-4.5">
                {a.icon}
              </span>
              <span className="mono-xs text-sand-deep">{a.index}</span>
            </div>
            <h3 className="display-sm mt-4">{a.title}</h3>
            <Badge variant="mono" className="mt-2 w-fit">
              {a.model}
            </Badge>
            <p className="mt-3 text-sm leading-relaxed text-ink-muted">{a.text}</p>
          </div>
        ))}
      </div>
    </Section>
  );
}
