import type { Procedure } from "./types";

export function matchProcedures(query: string, procedures: Procedure[]): Procedure[] {
  const q = query.trim().toLowerCase();
  if (!q) return procedures;

  const scored = procedures
    .map((p) => {
      let score = 0;
      if (p.slug === q) score += 100;
      if (p.plainName.toLowerCase() === q) score += 90;
      if (p.name.toLowerCase() === q) score += 85;
      if (p.plainName.toLowerCase().startsWith(q)) score += 60;
      if (p.plainName.toLowerCase().includes(q)) score += 40;
      if (p.searchTerms.some((t) => t.toLowerCase() === q)) score += 70;
      if (p.searchTerms.some((t) => t.toLowerCase().startsWith(q))) score += 50;
      if (p.searchTerms.some((t) => t.toLowerCase().includes(q))) score += 30;
      if (p.cptCodes.some((c) => c === q)) score += 80;
      if (p.category.toLowerCase().includes(q)) score += 15;
      return { p, score };
    })
    .filter(({ score }) => score > 0)
    .sort((a, b) => b.score - a.score);

  return scored.map(({ p }) => p);
}

export function resolveProcedureSlug(
  input: string,
  procedures: Procedure[],
): string {
  const q = input.trim();
  if (!q) return "";
  const bySlug = procedures.find((p) => p.slug === q);
  if (bySlug) return bySlug.slug;
  const matches = matchProcedures(q, procedures);
  if (matches[0]) return matches[0].slug;
  return q.toLowerCase().replace(/\s+/g, "-");
}