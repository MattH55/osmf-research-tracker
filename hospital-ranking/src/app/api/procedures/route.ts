import { NextResponse } from "next/server";
import { getProcedures } from "@/lib/data";

export async function GET() {
  const procedures = getProcedures().map((p) => ({
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