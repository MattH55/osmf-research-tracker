import { NextRequest, NextResponse } from "next/server";
import { getProcedures } from "@/lib/data";
import { matchProcedures } from "@/lib/procedure-match";

export async function GET(request: NextRequest) {
  const q = request.nextUrl.searchParams.get("q") ?? "";
  const all = getProcedures();
  const matched = q ? matchProcedures(q, all) : all;
  const procedures = matched.map((p) => ({
    id: p.id,
    slug: p.slug,
    plainName: p.plainName,
    name: p.name,
    category: p.category,
    cptCodes: p.cptCodes,
    drgCodes: p.drgCodes,
    searchTerms: p.searchTerms,
  }));
  return NextResponse.json({ procedures, count: procedures.length });
}