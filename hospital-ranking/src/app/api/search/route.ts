import { NextRequest, NextResponse } from "next/server";
import { searchHospitals } from "@/lib/search";
import type { InsuranceType } from "@/lib/types";

export async function GET(request: NextRequest) {
  const sp = request.nextUrl.searchParams;
  const procedure = sp.get("procedure") ?? "";
  const zip = sp.get("zip") ?? "";

  if (!procedure || !zip) {
    return NextResponse.json(
      { error: "procedure and zip are required" },
      { status: 400 },
    );
  }

  const { results, warnings, ...meta } = searchHospitals({
    procedure,
    zip,
    radiusMiles: Number(sp.get("radius")) || 50,
    minStars: Number(sp.get("minStars")) || 0,
    maxPrice: sp.get("maxPrice") ? Number(sp.get("maxPrice")) : undefined,
    insurance: (sp.get("insurance") as InsuranceType) ?? "cash",
    sort: (sp.get("sort") as "distance" | "price" | "quality") ?? "distance",
  });

  return NextResponse.json({
    ...meta,
    count: results.length,
    warnings,
    results: results.map((r) => ({
      hospitalId: r.hospital.id,
      hospitalName: r.hospital.name,
      distanceMiles: Math.round(r.distanceMiles * 10) / 10,
      cmsOverallStars: r.hospital.cmsOverallStars,
      estimatedOop: r.estimatedOop,
      cashMedian: r.price?.cashMedian ?? null,
      hasPrice: Boolean(r.price),
    })),
  });
}