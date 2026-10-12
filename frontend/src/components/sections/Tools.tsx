import { Section } from "@/components/site/primitives";

/*
 * Les outils de navigation de l'agent (backend/tools/tools.py). Limites : corpus de 84 rapports,
 * expérience LangSmith « … · agentic · 2026-10-12 14:26 ».
 */
const tools = [
  {
    verb: "Trouver",
    signature: "search(query, doc)",
    text: "Relance le retrieval hybride du pipeline (BM25 + vecteurs, routage, rerank Cohere) avec une requête reformulée, sur tout le corpus ou un seul document. 8 extraits, chacun avec son document et sa page.",
  },
  {
    verb: "Ouvrir",
    signature: "open_doc(doc)",
    text: "Le plan du rapport — PART, ITEM, états financiers consolidés, notes — avec la page de chaque section. Le modèle sait où chercher avant de chercher.",
  },
  {
    verb: "Naviguer",
    signature: "navigate(doc, section)",
    text: "Une section par son titre : « consolidated balance sheet » mène à la page du bilan, là où grep renverrait aussi le sommaire et chaque renvoi.",
  },
  {
    verb: "Localiser",
    signature: "grep(pattern, doc)",
    text: "Toutes les occurrences littérales d'un terme, page par page, sur les 260 pages. Exhaustif : zéro résultat permet d'affirmer qu'une donnée est absente du rapport, au lieu de le supposer.",
  },
  {
    verb: "Lire",
    signature: "read_page(doc, page, end_page)",
    text: "La page entière telle que l'OCR l'a produite, tableau compris, sur 1 à 3 pages quand il est à cheval. Ce qu'un chunk de 1 200 caractères ne montre jamais.",
  },
];

/*
 * Avec et sans outils de navigation, mêmes 65 questions, même modèle (Claude Sonnet 4.6), même
 * retrieval : expérience LangSmith « … · 2026-10-12 13:16 », baseline et agentic du même run.
 * Correctes : 35 → 54 (53,8 → 83,1 %). Fausses ou refusées : 30 (15 + 15) → 11 (11 + 0).
 * Latence de génération moyenne : 7,0 s → 10,99 s.
 * Coût : run avec outils seul « … · agentic · 2026-10-12 13:46 », Claude Sonnet 4.6 : 1 151 565 tokens
 * en entrée + 58 351 en sortie pour 65 questions = 4,33 $ (3 $ / 15 $ par million, Bedrock), soit
 * 0,067 $ et ~17 700 tokens par question (mesuré, juge non compris). Sans outils : ~3 000 tokens et
 * ~0,02 $, estimés par différence avec le run des deux modes (13:16).
 */
const toolGains = [
  {
    value: "+29 pts pour +4 s",
    label: "de réponses correctes, pour 4 secondes de plus",
    detail: "53,8 % → 83,1 % de réponses correctes ; 7,0 s → 11,0 s de génération par question en moyenne",
  },
  {
    value: "−63 %",
    label: "de réponses fausses ou refusées",
    detail: "30 sur 65 sans outils de navigation (15 fausses, 15 refus) → 11 avec (11 fausses, aucun refus)",
  },
  {
    value: "≈ 0,07 $",
    label: "par question, ≈ 18 000 tokens",
    detail: "Claude Sonnet 4.6 au tarif Bedrock, mesuré · sans outils de navigation : ≈ 3 000 tokens et ≈ 0,02 $ (estimation)",
  },
];

const limits = [
  {
    title: "Le recall du retrieval",
    text: "Sur les 84 rapports, la page de preuve est dans les 20 premiers passages pour 70 % des questions seulement. Les outils la font parvenir au modèle dans 89 % des cas : le reste est perdu avant même de répondre.",
  },
  {
    title: "Le routage",
    text: "Quand la question ne nomme pas clairement l'entreprise, ou la nomme d'une façon que le routeur ne reconnaît pas, il peut viser les mauvais rapports parmi 84 : l'agent répond alors avec les chiffres d'une autre entreprise, ou refuse.",
  },
  {
    title: "Les conventions de calcul",
    text: "Quick ratio, fonds de roulement, rotation des stocks : les références du benchmark n'appliquent pas toujours la même formule d'une question à l'autre. L'agent donne la convention principale et l'autre entre parenthèses ; le juge ne retient parfois que la première.",
  }
];

export function Tools() {
  return (
    <Section
      id="outils"
      index="03"
      eyebrow="Le levier déterminant"
      title={
        <>
          Ce RAG agentique ne se contente pas des passages qu&apos;on lui donne
          : il <span className="accent-italic">va chercher la preuve</span>,
          grâce à des outils.
        </>
      }
      intro="Un RAG classique choisit dix passages avant que le modèle ne lise la question, puis lui demande de répondre en une seule passe. Ici l'approche est différente, l'agent peut lui-même venir lire les documents, analyser un tableau, le contexte autour, partir, revenir, ect."
    >
      {/* d'où ça vient */}

      {/* les cinq outils */}
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {tools.map((t, i) => (
          <div
            key={t.signature}
            className="card-paper border-hairline flex h-full flex-col p-6"
          >
            <div className="flex items-center justify-between">
              <span className="eyebrow">{t.verb}</span>
              <span className="mono-xs text-ink-faint">0{i + 1}</span>
            </div>
            <code className="mono-xs mt-3 w-fit rounded-sm bg-brand-surface px-2 py-1 text-brand-deep">
              {t.signature}
            </code>
            <p className="mb-4 mt-3 text-sm leading-relaxed text-ink-muted">
              {t.text}
            </p>
          </div>
        ))}
      </div>

      <div className="card-paper border-hairline mt-10 p-8">
        <p className="display-sm mt-8">Voici les gains avec les outils de navigation</p>
        <p className="meta mt-1">
          Ce RAG, Claude Sonnet 4.6 · FinanceBench, mêmes 65 questions avec et sans outils de navigation
        </p>
        <div className="mt-6 grid gap-6 sm:grid-cols-3">
          {toolGains.map((g) => (
            <div key={g.label} className="border-l-2 border-brand pl-4">
              <div className="font-display text-4xl font-normal tracking-tight tabular-nums">
                {g.value}
              </div>
              <div className="mt-1 text-sm font-medium">{g.label}</div>
              <div className="meta mt-1">{g.detail}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-14">
        <div className="flex flex-col">
          <p className="display-md mt-3">Ce qui limite encore</p>
          <ol className="mt-6 divide-y divide-border border-t border-hairline">
            {limits.map((l, i) => (
              <li
                key={l.title}
                className="grid gap-1 py-4 sm:grid-cols-[2rem_16rem_1fr] sm:gap-4"
              >
                <span className="mono-xs pt-1 text-ink-faint">0{i + 1}</span>
                <span className="text-sm font-medium">{l.title}</span>
                <span className="text-sm leading-relaxed text-ink-muted">
                  {l.text}
                </span>
              </li>
            ))}
          </ol>
          <p className="mt-4 border-t border-sand pt-3 text-xs leading-relaxed text-muted-foreground">
            135 questions jugées sur 84 rapports : l'intervalle de confiance à
            95 % de l'exactitude va de 82 à 93 %.
          </p>
        </div>
      </div>
    </Section>
  );
}
