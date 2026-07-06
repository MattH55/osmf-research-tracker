"""NPASS — local SQLite bioactivity database."""
from __future__ import annotations

import logging
import sqlite3

log = logging.getLogger(__name__)


def query_for_disease_targets(
    target_genes: list[str],
    db: sqlite3.Connection | None,
) -> list[dict]:
    if not db or not target_genes:
        return []
    placeholders = ",".join("?" * len(target_genes))
    try:
        cur = db.execute(
            f"""
            SELECT DISTINCT c.compound_name, c.pubchem_cid, c.npass_id,
                   a.target_gene, a.activity_type, a.activity_value, a.activity_unit
            FROM activities a
            JOIN compounds c ON a.compound_id = c.compound_id
            WHERE a.target_gene IN ({placeholders})
              AND a.activity_value <= 10000
            ORDER BY a.activity_value ASC
            LIMIT 200
            """,
            target_genes,
        )
        return [
            {
                "compound_name": r[0],
                "pubchem_cid": r[1],
                "npass_id": r[2],
                "target_gene": r[3],
                "activity_type": r[4],
                "activity_value_nM": r[5],
                "activity_unit": r[6],
                "source": "NPASS",
            }
            for r in cur.fetchall()
        ]
    except sqlite3.Error as e:
        log.debug("[NPASS] query failed: %s", e)
        return []