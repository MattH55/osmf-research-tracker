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

# The GWAS Catalog legacy REST API (/gwas/rest/api/studies, .../associations)
# now returns HTTP 410 on every path, as does the old bulk summary-statistics
# API (spec section 4); neither may be called. Two v2 services remain:
#   - GWAS_CATALOG_REST_V2_BASE: the documented REST API v2 (snake_case JSON;
#     docs at https://www.ebi.ac.uk/gwas/rest/api/v2/docs), used for
#     studies-by-PubMed-ID and association queries
#   - GWAS_CATALOG_V2_BASE: the camelCase v2 service behind the web UI, used
#     only by study_v2(); it silently ignores unknown filters such as
#     accession_id (returns the whole catalogue), so filter names matter
GWAS_CATALOG_REST_V2_BASE = "https://www.ebi.ac.uk/gwas/rest/api/v2"
GWAS_CATALOG_V2_BASE = "https://www.ebi.ac.uk/gwas/api/v2"
EUROPEPMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
ENSEMBL_BASE = "https://rest.ensembl.org"
OLS_BASE = "https://www.ebi.ac.uk/ols4/api"
