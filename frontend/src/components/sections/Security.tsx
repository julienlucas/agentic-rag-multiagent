import { Globe2, Lock, Trash2 } from "lucide-react";
import { Section } from "@/components/site/primitives";

const points = [
  {
    icon: <Lock />,
    title: "Un espace isolé par compte",
    text: "Vos documents et leurs index ne sont lisibles que depuis votre compte : chaque recherche est filtrée sur votre espace, côté serveur.",
  },
  {
    icon: <Globe2 />,
    title: "Données hébergées en Europe",
    text: "Fichiers, index et modèles (Amazon Bedrock à Paris et Francfort) restent dans l'Union européenne.",
  },
  {
    icon: <Trash2 />,
    title: "Supprimé, c'est supprimé",
    text: "Supprimer un document efface l'original et son index ; supprimer le compte efface tout.",
  },
];

export function Security() {
  return (
    <Section
      id="securite"
      index="06"
      eyebrow="Sécurité"
      title={
        <>
          Vos documents restent <span className="accent-italic">les vôtres</span>.
        </>
      }
    >
      <div className="grid gap-4 md:grid-cols-3">
        {points.map((p) => (
          <div key={p.title} className="card-paper flex flex-col p-6">
            <span className="inline-flex size-9 items-center justify-center rounded-md bg-brand-surface text-brand-deep [&_svg]:size-4.5">
              {p.icon}
            </span>
            <h3 className="display-sm mt-4">{p.title}</h3>
            <p className="mt-3 text-sm leading-relaxed text-ink-muted">{p.text}</p>
          </div>
        ))}
      </div>
    </Section>
  );
}
