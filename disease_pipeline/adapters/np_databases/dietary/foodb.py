"""FooDB — food compound bioactivities (local SQLite)."""
from __future__ import annotations

import logging
import sqlite3

log = logging.getLogger(__name__)


def query_disease(
    disease_name: str,
    db: sqlite3.Connection | None,
    activity_terms: list[str],
) -> list[dict]:
    if not db or not activity_terms:
        return []
    placeholders = ",".join("?" * len(activity_terms))
    try:
        cur = db.execute(
            f"""
            SELECT DISTINCT c.name, c.public_id, c.inchikey,
                   GROUP_CONCAT(DISTINCT f.name) as food_sources,
                   cb.activity_type
            FROM compound_bioactivities cb
            JOIN compounds c ON cb.compound_id = c.id
            LEFT JOIN food_compounds fc ON fc.compound_id = c.id
            LEFT JOIN foods f ON fc.food_id = f.id
            WHERE cb.activity_type IN ({placeholders})
            GROUP BY c.id
            LIMIT 100
            """,
            activity_terms,
        )
        return [
            {
                "compound_name": r[0],
                "foodb_id": r[1],
                "inchikey": r[2],
                "food_sources": (r[3] or "").split(",") if r[3] else [],
                "activity_type": r[4],
                "source": "FooDB",
            }
            for r in cur.fetchall()
        ]
    except sqlite3.Error as e:
        log.debug("[FooDB] query failed: %s", e)
        return []