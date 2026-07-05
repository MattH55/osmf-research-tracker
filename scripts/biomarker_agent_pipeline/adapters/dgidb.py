"""DGIdb GraphQL adapter."""
from __future__ import annotations

from ..http_util import request_json
from ..models import NormalizedBiomarker, RawHit

DGIDB_URL = "https://dgidb.org/api/graphql"

QUERY = """
query GeneInteractions($names: [String!]!) {
  genes(names: $names) {
    nodes {
      name
      interactions {
        interactionScore
        interactionTypes { type directionality }
        interactionClaims { name directionality }
        drug { name conceptId }
        sources { sourceDbName sourceUrl }
        publications { pmid }
      }
    }
  }
}
"""


def query_dgidb(norm: NormalizedBiomarker) -> list[RawHit]:
    if not norm.symbol:
        return []
    names = list(dict.fromkeys([norm.symbol, *(norm.synonyms[:3])]))[:3]
    data = request_json(
        "dgidb",
        norm.symbol,
        "POST",
        DGIDB_URL,
        json_body={"query": QUERY, "variables": {"names": names}},
        headers={"Content-Type": "application/json"},
    )
    hits: list[RawHit] = []
    nodes = (data.get("data") or {}).get("genes", {}).get("nodes", [])
    for node in nodes:
        for inter in node.get("interactions", []):
            drug = inter.get("drug") or {}
            agent = drug.get("name")
            if not agent:
                continue
            types = inter.get("interactionTypes") or []
            claims = inter.get("interactionClaims") or []
            itype = None
            direction = None
            if types:
                itype = types[0].get("type")
                direction = types[0].get("directionality")
            elif claims:
                itype = claims[0].get("name")
                direction = claims[0].get("directionality")
            sources = inter.get("sources") or []
            url = (sources[0].get("sourceUrl") if sources else None) or "https://dgidb.org/"
            hits.append(
                RawHit(
                    agent=agent,
                    agent_id=drug.get("conceptId"),
                    interaction_type=itype,
                    direction_hint=direction,
                    source="DGIdb",
                    source_url=url,
                    raw=inter,
                )
            )
    return hits