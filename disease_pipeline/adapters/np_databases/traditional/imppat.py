"""IMPPAT — Indian medicinal plants (local SQLite)."""
from __future__ import annotations

import logging
import sqlite3

log = logging.getLogger(__name__)


def query_imppat_for_disease(disease_name: str, db: sqlite3.Connection | None) -> list[dict]:
    if db is None:
        return []
    disease_lower = disease_name.lower()
    try:
        cur = db.execute(
            """
            SELECT DISTINCT c.chem_name, c.pubchem_cid, p.plant_name_en,
                   GROUP_CONCAT(DISTINCT a.target_gene) as targets,
                   d.traditional_use
            FROM disease_links d
            JOIN plants p ON d.plant_id = p.plant_id
            JOIN chemicals c ON c.plant_id = p.plant_id
            LEFT JOIN activities a ON a.chem_id = c.chem_id
            WHERE LOWER(d.disease_name) LIKE ?
            GROUP BY c.chem_id
            LIMIT 100
            """,
            (f"%{disease_lower}%",),
        )
        return [
            {
                "chemical_name": r[0],
                "pubchem_cid": r[1],
                "source_plant": r[2],
                "target_genes": (r[3] or "").split(",") if r[3] else [],
                "traditional_use": r[4],
                "source": "IMPPAT",
            }
            for r in cur.fetchall()
        ]
    except sqlite3.Error as e:
        log.debug("[IMPPAT] query failed: %s", e)
        return []


async def query_disease(disease_name: str, db: sqlite3.Connection | None) -> list[dict]:
    return query_imppat_for_disease(disease_name, db)