/**
 * Retrouver un passage cité dans le texte d'une page, pour le surligner.
 *
 * Le passage vient de l'OCR (markdown, tableaux en `| … |`) et la page du texte du PDF
 * (pdf.js) ou de l'OCR : les deux ne coïncident pas caractère pour caractère. On compare
 * donc des suites de trois mots (trigrammes), chiffres normalisés (« 23,601 » = « 23601 »),
 * comme le recalage des pages côté backend (markdown_corpus.py).
 */

export function tokens(text: string): string[] {
  const normalized = text.toLowerCase().replace(/(?<=\d),(?=\d{3})/g, "");
  return normalized.match(/\p{L}+|\d+(?:\.\d+)?/gu) ?? [];
}

function ngrams(toks: string[], n: number): string[] {
  const out: string[] = [];
  for (let i = 0; i + n <= toks.length; i++) out.push(toks.slice(i, i + n).join(" "));
  return out;
}

/**
 * Pour une suite de segments (éléments de texte pdf.js, lignes OCR), ceux qui font partie du
 * passage. Un segment l'est si au moins la moitié de ses mots tombent dans un trigramme du
 * passage. Parmi les zones ainsi marquées, on ne garde que la plus fournie : une formule
 * courante (« in millions of ») ailleurs sur la page ne doit pas être surlignée.
 */
export function matchSegments(segments: string[], passage: string): boolean[] {
  const passageTokens = tokens(passage);
  const n = Math.min(3, passageTokens.length);
  const result = segments.map(() => false);
  if (n === 0) return result;
  const wanted = new Set(ngrams(passageTokens, n));

  const owner: number[] = [];
  const all: string[] = [];
  const counts = segments.map((s, i) => {
    const toks = tokens(s);
    toks.forEach((t) => {
      all.push(t);
      owner.push(i);
    });
    return toks.length;
  });

  const hit = new Array(all.length).fill(false);
  for (let i = 0; i + n <= all.length; i++) {
    if (wanted.has(all.slice(i, i + n).join(" "))) for (let k = i; k < i + n; k++) hit[k] = true;
  }
  const hits = segments.map(() => 0);
  hit.forEach((h, k) => {
    if (h) hits[owner[k]] += 1;
  });
  const marked = counts.map((c, i) => c > 0 && hits[i] / c >= 0.5);

  // Zones de segments marqués, tolérant deux segments non marqués (vides, puces, numéros).
  let best = { from: -1, to: -1, score: 0 };
  let zone = { from: -1, to: -1, score: 0 };
  let gap = 0;
  marked.forEach((m, i) => {
    if (m) {
      if (zone.from < 0) zone = { from: i, to: i, score: 0 };
      zone.to = i;
      zone.score += hits[i];
      gap = 0;
    } else if (zone.from >= 0 && counts[i] > 0 && ++gap > 2) {
      if (zone.score > best.score) best = zone;
      zone = { from: -1, to: -1, score: 0 };
      gap = 0;
    }
  });
  if (zone.score > best.score) best = zone;
  // Dans la zone, les segments sans mot (« $ », « — », parenthèses) suivent leurs voisins.
  for (let i = best.from; i >= 0 && i <= best.to; i++) {
    result[i] = marked[i] || (counts[i] === 0 && segments[i].trim() !== "");
  }
  return result;
}
