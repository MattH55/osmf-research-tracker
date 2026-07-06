#!/usr/bin/env python3
"""Load IMPPAT / NPASS / FooDB TSV dumps into SQLite seeds."""
from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent
SEEDS = ROOT / "seeds"


def load_imppat(tsv_dir: Path, db_path: Path) -> None:
    db = sqlite3.connect(str(db_path))
    db.executescript("""
    CREATE TABLE IF NOT EXISTS plants (plant_id TEXT, plant_name_en TEXT, plant_name_san TEXT, common_names TEXT);
    CREATE TABLE IF NOT EXISTS chemicals (chem_id TEXT, chem_name TEXT, pubchem_cid TEXT, plant_id TEXT);
    CREATE TABLE IF NOT EXISTS activities (chem_id TEXT, activity_type TEXT, target_gene TEXT, reference TEXT);
    CREATE TABLE IF NOT EXISTS disease_links (plant_id TEXT, disease_name TEXT, traditional_use TEXT);
    """)
    for table, fname, cols in (
        ("plants", "IMPPAT_plant_details.tsv", ["plant_id", "plant_name_en", "plant_name_san", "common_names"]),
        ("chemicals", "IMPPAT_phytochemical_details.tsv", ["chem_id", "chem_name", "pubchem_cid", "plant_id"]),
        ("activities", "IMPPAT_activities.tsv", ["chem_id", "activity_type", "target_gene", "reference"]),
        ("disease_links", "IMPPAT_disease_annotations.tsv", ["plant_id", "disease_name", "traditional_use"]),
    ):
        path = tsv_dir / fname
        if not path.exists():
            continue
        db.execute(f"DELETE FROM {table}")
        with path.open(encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                vals = [row.get(c, "") for c in cols]
                db.execute(
                    f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?'*len(cols))})",
                    vals,
                )
    db.commit()
    db.close()
    print(f"IMPPAT loaded -> {db_path}")


def load_npass(tsv_dir: Path, db_path: Path) -> None:
    db = sqlite3.connect(str(db_path))
    db.executescript("""
    CREATE TABLE IF NOT EXISTS compounds (compound_id TEXT, compound_name TEXT, pubchem_cid TEXT, npass_id TEXT);
    CREATE TABLE IF NOT EXISTS activities (compound_id TEXT, target_gene TEXT, activity_type TEXT,
        activity_value REAL, activity_unit TEXT, organism_id TEXT);
    CREATE TABLE IF NOT EXISTS organisms (organism_id TEXT, species_name TEXT);
    """)
    for table, fname in (
        ("compounds", "NPASS_compounds.tsv"),
        ("activities", "NPASS_activities.tsv"),
        ("organisms", "NPASS_organisms.tsv"),
    ):
        path = tsv_dir / fname
        if not path.exists():
            continue
        db.execute(f"DELETE FROM {table}")
        with path.open(encoding="utf-8", errors="replace", newline="") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                db.execute(f"INSERT INTO {table} VALUES ({','.join('?'*len(row))})", list(row.values()))
    db.commit()
    db.close()
    print(f"NPASS loaded -> {db_path}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--imppat-dir", type=Path, help="Directory with IMPPAT TSV files")
    p.add_argument("--npass-dir", type=Path, help="Directory with NPASS TSV files")
    args = p.parse_args()
    if args.imppat_dir:
        load_imppat(args.imppat_dir, SEEDS / "imppat.db")
    if args.npass_dir:
        load_npass(args.npass_dir, SEEDS / "npass.db")
    if not args.imppat_dir and not args.npass_dir:
        print("Provide --imppat-dir and/or --npass-dir with downloaded TSV files")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())