/**
 * Parse le rapport de vérification renvoyé par le backend
 * (backend/agents/workflow.py :: build_verification_report) en signaux structurés.
 * Le rapport est un texte markdown ligne par ligne, construit sans appel LLM,
 * à partir des vrais signaux du pipeline.
 */

export type Relevance = "CAN_ANSWER" | "PARTIAL" | "NO_MATCH";

export type VerificationSignals = {
  raw: string;
  relevant: boolean | null;
  relevance: Relevance | null;
  relevanceLabel: string | null;
  rerankScore: number | null;
  rerankLevel: "élevée" | "moyenne" | "faible" | null;
  correctiveRounds: number;
  correctiveQueries: string[];
  sources: { name: string; pages: number[] }[];
  passagesCount: number | null;
  error: string | null;
};

const strip = (s: string) => s.replace(/\*\*/g, "").trim();

export function parseVerificationReport(report: string): VerificationSignals {
  const out: VerificationSignals = {
    raw: report || "",
    relevant: null,
    relevance: null,
    relevanceLabel: null,
    rerankScore: null,
    rerankLevel: null,
    correctiveRounds: 0,
    correctiveQueries: [],
    sources: [],
    passagesCount: null,
    error: null,
  };
  if (!report) return out;

  for (const rawLine of report.split("\n")) {
    const line = rawLine.trim();
    if (!line) continue;

    if (/^Erreur\s*:/i.test(line)) {
      out.error = line.replace(/^Erreur\s*:\s*/i, "");
      continue;
    }

    const bullet = /^•\s*\*?(.+?)\*?$/.exec(line);
    if (bullet) {
      out.correctiveQueries.push(bullet[1].replace(/^\*|\*$/g, ""));
      continue;
    }

    const kv = /^\*\*(.+?):\*\*\s*(.*)$/.exec(line);
    if (!kv) continue;
    const key = kv[1].toLowerCase();
    const value = strip(kv[2]);

    if (key === "pertinent") {
      out.relevant = /^oui/i.test(value);
    } else if (key.startsWith("pertinence des passages")) {
      const m = /^(CAN_ANSWER|PARTIAL|NO_MATCH)\s*(?:—|-)?\s*(.*)$/.exec(value);
      if (m) {
        out.relevance = m[1] as Relevance;
        out.relevanceLabel = m[2] || null;
      }
    } else if (key.startsWith("confiance retrieval")) {
      const m = /([\d.,]+)\s*(?:—|-)?\s*(élevée|moyenne|faible)?/.exec(value);
      if (m) {
        out.rerankScore = parseFloat(m[1].replace(",", "."));
        out.rerankLevel = (m[2] as VerificationSignals["rerankLevel"]) || null;
      }
    } else if (key.startsWith("recherche corrective")) {
      const m = /déclenchée\s*\((\d+)/.exec(value);
      out.correctiveRounds = m ? parseInt(m[1], 10) : 0;
    } else if (key.startsWith("sources utilisées")) {
      const [list, tail] = value.split(/\s+—\s+/);
      const pc = /(\d+)\s+passages?/.exec(tail || "");
      if (pc) out.passagesCount = parseInt(pc[1], 10);
      out.sources = (list || "")
        .split(" · ")
        .map((s) => s.trim())
        .filter(Boolean)
        .map((s) => {
          const m = /^(.*?)\s*\(p\.\s*([^)]*)\)\s*$/.exec(s);
          if (!m) return { name: s, pages: [] };
          const pages = m[2]
            .split(",")
            .map((p) => parseInt(p.trim(), 10))
            .filter((n) => !Number.isNaN(n));
          return { name: m[1].trim(), pages };
        });
    }
  }

  return out;
}
