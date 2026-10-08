"""CSV <-> pydantic model loading for the flat-file tables under data/genetics/."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Type, TypeVar

from pydantic import BaseModel

from . import models
from .config import DATA_DIR

T = TypeVar("T", bound=BaseModel)

MODEL_BY_TABLE: dict[str, Type[BaseModel]] = {
    "phenotypes": models.Phenotype,
    "phenotype_relationships": models.PhenotypeRelationship,
    "studies": models.Study,
    "variants": models.Variant,
    "associations": models.Association,
    "genes": models.Gene,
    "loci": models.Locus,
    "locus_gene": models.LocusGene,
    "sources": models.Source,
    "publications": models.Publication,
}

BOOL_TRUE = {"true", "1", "yes"}
BOOL_FALSE = {"false", "0", "no"}


def _coerce_row(row: dict, model: Type[BaseModel]) -> dict:
    """Empty CSV cells are dropped so the field's own default applies
    (None, "" or otherwise); bare true/false strings become bool for bool
    fields."""
    fields = model.model_fields
    out = {}
    for k, v in row.items():
        if v == "" or v is None:
            continue  # let the model default apply
        field = fields.get(k)
        if field is not None and field.annotation is bool:
            out[k] = v.strip().lower() in BOOL_TRUE
        else:
            out[k] = v
    return out


def load_table(table: str) -> list[BaseModel]:
    model = MODEL_BY_TABLE[table]
    path = DATA_DIR / f"{table}.csv"
    rows: list[BaseModel] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(model(**_coerce_row(row, model)))
    return rows


def load_all() -> dict[str, list[BaseModel]]:
    return {table: load_table(table) for table in MODEL_BY_TABLE}


def write_json(obj, path: Path) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=False, default=str)
        f.write("\n")
