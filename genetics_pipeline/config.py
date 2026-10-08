"""Paths and constants shared across pipeline modules."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "genetics"
SITE_DIR = ROOT / "genetics"
SCHEMA_PATH = DATA_DIR / "genetic-correlate.schema.json"
MANIFEST_PATH = DATA_DIR / "manifest.json"

TABLES = [
    "phenotypes",
    "phenotype_relationships",
    "studies",
    "variants",
    "associations",
    "genes",
    "loci",
    "locus_gene",
    "sources",
    "publications",
]

GENOME_WIDE_SIGNIFICANCE = 5e-8
SUGGESTIVE_UPPER = 1e-5

# GWAS Catalog's legacy per-study associations endpoint still works for curated
# top hits; the old bulk summary-statistics API (spec section 4) returns 410 on
# every path and must never be called.
GWAS_CATALOG_LEGACY_BASE = "https://www.ebi.ac.uk/gwas/rest/api"
GWAS_CATALOG_V2_BASE = "https://www.ebi.ac.uk/gwas/api/v2"
EUROPEPMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
ENSEMBL_BASE = "https://rest.ensembl.org"
OLS_BASE = "https://www.ebi.ac.uk/ols4/api"
