"""API endpoints, rate limits, and cache configuration."""
import json
import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).parent
CACHE_DIR = PACKAGE_DIR / "cache"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
SEEDS_PATH = PACKAGE_DIR / "seeds" / "disease_ids.json"
SECRETS_PATH = PACKAGE_DIR.parent / "config" / "secrets.local.json"

NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")
DISGENET_API_KEY = os.getenv("DISGENET_API_KEY", "")

CACHE_TTL_DAYS = 7
HTTP_TIMEOUT = 25.0
CLINICALTRIALS_TIMEOUT = 30.0
DEFAULT_CT_CONTACT_EMAIL = "matt.halma@gmail.com"
USER_AGENT = f"DiseasePipeline/1.0 ({DEFAULT_CT_CONTACT_EMAIL})"

RATE_LIMITS: dict[str, float] = {
    "open_targets": 10,
    "disgenet": 1,
    "hpo": 5,
    "orphanet": 5,
    "clinicaltrials": 1,
    "chembl": 10,
    "dgidb": 5,
    "pubmed": 10 if NCBI_API_KEY else 3,
    "hmdb": 2,
    "pubchem": 5,
    "lotus": 5,
    "anthropic": 20,
    "greenmedinfo": 1,
    "examine": 1,
    "default": 5,
}

OPEN_TARGETS_URL = "https://api.platform.opentargets.org/api/v4/graphql"
DISGENET_URL = "https://www.disgenet.org/api"
HPO_URL = "https://hpo.jax.org/api"
ORPHANET_OLS_URL = "https://www.ebi.ac.uk/ols4/api"
CLINICALTRIALS_URL = "https://clinicaltrials.gov/api/v2"
CHEMBL_URL = "https://www.ebi.ac.uk/chembl/api/data"
DGIDB_URL = "https://dgidb.org/api/graphql"
PUBMED_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
OXO_URL = "https://www.ebi.ac.uk/spot/oxo/api"
MONARCH_API = "https://api.monarchinitiative.org/v3/api"
ORPHADATA_PHENOTYPES = "https://api.orphadata.com/rd-phenotypes/orphaid"
LOINC_SEARCH = "https://clinicaltables.nlm.nih.gov/api/loinc/v3/search"
HMDB_SEARCH = "https://hmdb.ca/unearth/q"
UNIPROT_SEARCH = "https://rest.uniprot.org/uniprotkb/search"
LOTUS_BASE = "https://lotus.naturalproducts.net/api"
PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
NP_SYNONYMS_PATH = PACKAGE_DIR / "seeds" / "np_synonyms.json"
NP_SAFETY_PATH = PACKAGE_DIR / "seeds" / "np_safety.json"


def _load_secret(key: str) -> str:
    env_val = os.getenv(key, "")
    if env_val:
        return env_val
    if SECRETS_PATH.exists():
        try:
            secrets = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
            return secrets.get(key, "") or ""
        except (json.JSONDecodeError, OSError):
            pass
    return ""


def get_ncbi_api_key() -> str:
    return _load_secret("NCBI_API_KEY") or NCBI_API_KEY


def get_disgenet_api_key() -> str:
    return _load_secret("DISGENET_API_KEY") or DISGENET_API_KEY


def get_clinicaltrials_contact_email() -> str:
    return (
        _load_secret("CLINICALTRIALS_CONTACT_EMAIL")
        or os.getenv("CLINICALTRIALS_CONTACT_EMAIL", "")
        or DEFAULT_CT_CONTACT_EMAIL
    )


def get_clinicaltrials_user_agent() -> str:
    return f"DiseasePipeline/1.0 ({get_clinicaltrials_contact_email()})"


def clinicaltrials_headers() -> dict[str, str]:
    return {
        "User-Agent": get_clinicaltrials_user_agent(),
        "Accept": "application/json",
    }


def get_anthropic_api_key() -> str:
    return _load_secret("ANTHROPIC_API_KEY")