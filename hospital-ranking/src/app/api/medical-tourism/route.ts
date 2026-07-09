import { NextRequest, NextResponse } from "next/server";
import { getProcedure } from "@/lib/data";
import { getTourismEstimates, TOURISM_METHODOLOGY } from "@/lib/medical-tourism";

export async function GET(request: NextRequest) {
  const procedureSlug = request.nextUrl.searchParams.get("procedure") ?? "";
  const usBaseline = request.nextUrl.searchParams.get("usBaseline");
  const procedure = getProcedure(procedureSlug);

  if (!procedure) {
    return NextResponse.json(
      { error: "procedure is required and must match a known procedure slug" },
      { status: 400 },
    );
  }

  const baseline = usBaseline ? Number(usBaseline) : undefined;
  const estimates = getTourismEstimates(procedure.id, {
    usBaseline: baseline && baseline > 0 ? baseline : undefined,
  });

  return NextResponse.json({
    procedure: {
      id: procedure.id,
      slug: procedure.slug,
      plainName: procedure.plainName,
    },
    methodology: TOURISM_METHODOLOGY,
    count: estimates.length,
    estimates: estimates.map((e) => ({
      destinationId: e.destinationId,
      country: e.destination.country,
      flagEmoji: e.destination.flagEmoji,
      hubCities: e.destination.hubCities,
      cashLow: e.cashLow,
      cashMedian: e.cashMedian,
      cashHigh: e.cashHigh,
      usReferenceMedian: e.usReferenceMedian,
      savingsPercent: e.savingsPercent,
      packageIncludes: e.packageIncludes,
      packageExcludes: e.packageExcludes,
      accreditationNote: e.destination.accreditationNote,
      travelFromUs: e.destination.travelFromUs,
      clinics: e.destination.clinics,
      priceSource: e.priceSource,
      priceVintage: e.priceVintage,
    })),
  });
}