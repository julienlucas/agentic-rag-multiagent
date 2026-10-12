import { FileUp, MessageSquareQuote, Search } from "lucide-react";
import { Section } from "@/components/site/primitives";
import { usePricing } from "@/lib/session";

/** Les formats, regroupés par famille pour la lecture. */
export function formatFamilies(formats: string[]) {
  const families: [string, string[]][] = [
    ["PDF", [".pdf"]],
    ["Bureautique", [".docx", ".pptx", ".odt", ".odp", ".rtf", ".doc", ".ppt"]],
    ["Images", [".png", ".jpg", ".jpeg", ".webp"]],
    ["Texte", [".txt", ".md", ".markdown", ".html", ".htm"]],
    ["Tableurs", [".xlsx", ".csv"]],
  ];
  const known = new Set(families.flatMap(([, exts]) => exts));
  const rows = families
    .map(([name, exts]) => [name, exts.filter((e) => formats.includes(e))] as [string, string[]])
    .filter(([, exts]) => exts.length);
  const others = formats.filter((f) => !known.has(f));
  if (others.length) rows.push(["Autres", others]);
  return rows;
}

export function HowItWorks() {
  const pricing = usePricing();
  const steps = [
    {
      icon: <FileUp />,
      title: "Déposez vos documents",
      text: "Rapports, contrats, présentations, scans, tableurs : chaque fichier est lu page par page (OCR si besoin) et indexé dans votre espace, isolé de celui des autres.",
    },
    {
      icon: <Search />,
      title: "L'agent cherche",
      text: "Recherche hybride lexicale et vectorielle, reranking, puis cinq outils pour lire une page entière, chercher un terme exact ou naviguer dans le plan du document.",
    },
    {
      icon: <MessageSquareQuote />,
      title: "Une réponse citée, page à l'appui",
      text: "Chaque affirmation porte sa citation [n] ; un clic ouvre le document à la page citée. Si l'information n'y est pas, l'agent le dit.",
    },
  ];

  return (
    <Section
      id="fonctionnement"
      index="01"
      eyebrow="Fonctionnement"
      title={
        <>
          De vos fichiers à des <span className="accent-italic">réponses sourcées</span>.
        </>
      }
      intro="Trois étapes, aucun réglage. Le prix de chaque action est affiché avant de la lancer."
    >
      <ol className="grid gap-4 md:grid-cols-3">
        {steps.map((s, i) => (
          <li key={s.title} className="card-paper flex flex-col p-6">
            <div className="flex items-center justify-between">
              <span className="inline-flex size-9 items-center justify-center rounded-md bg-brand-surface text-brand-deep [&_svg]:size-4.5">
                {s.icon}
              </span>
              <span className="mono-xs text-ink-faint">0{i + 1}</span>
            </div>
            <h3 className="display-sm mt-4">{s.title}</h3>
            <p className="mt-3 text-sm leading-relaxed text-ink-muted">{s.text}</p>
          </li>
        ))}
      </ol>

      <div className="mt-10 overflow-x-auto">
        <table className="w-full min-w-[32rem] border-collapse text-sm">
          <caption className="mono-xs uppercase tracking-[0.09em] text-ink-faint mb-3 text-left">Formats acceptés</caption>
          <tbody>
            {formatFamilies(pricing.formats).map(([family, exts]) => (
              <tr key={family} className="border-t border-hairline">
                <th scope="row" className="w-40 py-3 pr-4 text-left font-medium text-ink">
                  {family}
                </th>
                <td className="py-3">
                  <span className="flex flex-wrap gap-1.5">
                    {exts.map((e) => (
                      <span key={e} className="tag normal-case">
                        {e}
                      </span>
                    ))}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  );
}
