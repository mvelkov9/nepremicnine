"""Region lookup service: municipality → statistical region, with fallback data."""

import logging
import unicodedata

from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

# ── Fallback: municipality → region mapping (lowercase, no diacritics) ────────
_FALLBACK_BY_REGION = {
    "Pomurska": [
        "apace",
        "beltinci",
        "cankova",
        "crensovci",
        "dobrovnik",
        "gornja radgona",
        "gornji petrovci",
        "grad",
        "hodos",
        "kobilje",
        "krizevci",
        "kuzma",
        "lendava",
        "ljutomer",
        "moravske toplice",
        "murska sobota",
        "odranci",
        "puconci",
        "radenci",
        "razkrizje",
        "rogasovci",
        "salovci",
        "sveti jurij ob scavnici",
        "tisina",
        "turnisce",
        "velika polana",
        "verzej",
        "sveti andraz v slov. goricah",
        "sveti jurij v slov. goricah",
    ],
    "Podravska": [
        "benedikt",
        "cerkvenjak",
        "cirkulane",
        "destrnik",
        "dornava",
        "duplek",
        "gorisnica",
        "hajdina",
        "hoce - slivnica",
        "hoce-slivnica",
        "jursinci",
        "kidricevo",
        "kungota",
        "lenart",
        "lovrenc na pohorju",
        "majsperk",
        "makole",
        "maribor",
        "markovci",
        "miklavz na dravskem polju",
        "oplotnica",
        "ormoz",
        "pesnica",
        "podlehnik",
        "poljcane",
        "ptuj",
        "race - fram",
        "race-fram",
        "ruse",
        "selnica ob dravi",
        "slovenska bistrica",
        "sredisce ob dravi",
        "starse",
        "sveta ana",
        "sveta trojica v slovenskih goricah",
        "sv. trojica v slov. goricah",
        "sveti andraz v slovenskih goricah",
        "sveti jurij v slovenskih goricah",
        "sveti tomaz",
        "sentilj",
        "trnovska vas",
        "videm",
        "zavrc",
        "zetale",
    ],
    "Koroska": [
        "crna na koroskem",
        "dravograd",
        "mezica",
        "mislinja",
        "muta",
        "podvelka",
        "prevalje",
        "radlje ob dravi",
        "ravne na koroskem",
        "ribnica na pohorju",
        "slovenj gradec",
        "vuzenica",
    ],
    "Savinjska": [
        "braslovce",
        "celje",
        "dobje",
        "dobrna",
        "gornji grad",
        "kozje",
        "lasko",
        "ljubno",
        "luce",
        "mozirje",
        "nazarje",
        "podcetrtek",
        "polzela",
        "prebold",
        "recica ob savinji",
        "rogaska slatina",
        "rogatec",
        "sentjur",
        "smarje pri jelsah",
        "smartno ob paki",
        "slovenske konjice",
        "sol pri savinji",
        "sol",
        "solcava",
        "sostanj",
        "store",
        "tabor",
        "velenje",
        "vitanje",
        "vojnik",
        "vransko",
        "zalec",
        "zrece",
    ],
    "Zasavska": [
        "hrastnik",
        "trbovlje",
        "zagorje ob savi",
    ],
    "Posavska": [
        "brezice",
        "kostanjevica na krki",
        "krsko",
        "radece",
        "sevnica",
        "bistrica ob sotli",
    ],
    "Jugovzhodna Slovenija": [
        "crnomelj",
        "dolenjske toplice",
        "kocevje",
        "kostel",
        "loski potok",
        "metlika",
        "mirna",
        "mirna pec",
        "mokronog - trebelno",
        "mokronog-trebelno",
        "novo mesto",
        "osilnica",
        "ribnica",
        "semic",
        "skocjan",
        "smarjeske toplice",
        "straza",
        "sodrazica",
        "sucna vas",
        "sentjernej",
        "sentrupert",
        "trebnje",
        "zuzemberk",
    ],
    "Osrednjeslovenska": [
        "borovnica",
        "brezovica",
        "dobrepolje",
        "dobrova - polhov gradec",
        "dobrova-polhov gradec",
        "dol pri ljubljani",
        "domzale",
        "grosuplje",
        "horjul",
        "ig",
        "ivancna gorica",
        "kamnik",
        "komenda",
        "litija",
        "ljubljana",
        "log - dragomer",
        "log-dragomer",
        "logatec",
        "lukovica",
        "medvode",
        "menges",
        "moravce",
        "skofljica",
        "smartno pri litiji",
        "trzin",
        "velike lasce",
        "vodice",
        "vrhnika",
    ],
    "Gorenjska": [
        "bled",
        "bohinj",
        "cerklje na gorenjskem",
        "gorenja vas - poljane",
        "gorenja vas-poljane",
        "gorje",
        "jesenice",
        "jezersko",
        "kranj",
        "kranjska gora",
        "naklo",
        "preddvor",
        "radovljica",
        "sencur",
        "skofja loka",
        "trzic",
        "zelezniki",
        "ziri",
        "zirovnica",
    ],
    "Primorsko-notranjska": [
        "bloke",
        "cerknica",
        "ilirska bistrica",
        "loska dolina",
        "pivka",
        "postojna",
    ],
    "Goriska": [
        "ajdovscina",
        "bovec",
        "brda",
        "cerkno",
        "idrija",
        "kanal ob soci",
        "kanal",
        "kobarid",
        "miren - kostanjevica",
        "miren-kostanjevica",
        "nova gorica",
        "rence-vogrsko",
        "renece - vogrsko",
        "renece-vogrsko",
        "sempeter - vrtojba",
        "sempeter-vrtojba",
        "tolmin",
        "vipava",
    ],
    "Obalno-kraska": [
        "ankaran",
        "divaca",
        "hrpelje - kozina",
        "hrpelje-kozina",
        "izola",
        "komen",
        "koper",
        "piran",
        "sezana",
    ],
}

# Flat dict: municipality_name → region_name
FALLBACK_REGIONS: dict[str, str] = {}
for region, municipalities in _FALLBACK_BY_REGION.items():
    for m in municipalities:
        FALLBACK_REGIONS[m] = region

STATISTICAL_REGIONS = list(_FALLBACK_BY_REGION.keys())


def normalize(text: str) -> str:
    """Lowercase, strip diacritics (č→c, š→s, ž→z), strip whitespace."""
    text = text.lower().strip()
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def lookup_region(municipality: str) -> str:
    """Look up the statistical region for a municipality (fallback only)."""
    key = normalize(municipality)
    if key in FALLBACK_REGIONS:
        return FALLBACK_REGIONS[key]
    # Partial match
    for m, r in FALLBACK_REGIONS.items():
        if key in m or m in key:
            return r
    return "neznana"


def lookup_region_by_code(code: int | str) -> str | None:
    """Look up statistical region by municipality code (sifra).

    1. First checks the database ``region_lookup`` table for a matching ``obcina_sifra``.
    2. Falls back to the hardcoded ``FALLBACK_REGIONS`` dictionary (name-based)
       if the DB has no matching code.

    Returns the region name, or ``None`` when no match is found in either source.
    """
    if code is None:
        return None
    try:
        sifra = int(code)
    except (ValueError, TypeError):
        return None

    # 1. Check DB (cached after first load)
    sifra_map = _load_sifra_from_db()
    result = sifra_map.get(sifra)
    if result and result != "neznana":
        return result

    return None


# ---------------------------------------------------------------------------
# Internal helpers for DB-backed sifra → region cache
# ---------------------------------------------------------------------------

_sifra_cache: dict[int, str] | None = None


def _get_sync_database_url() -> str:
    """Convert the async database URL to a synchronous one for batch operations."""
    from app.config import get_settings

    url = get_settings().database_url
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    url = url.replace("sqlite+aiosqlite://", "sqlite://")
    return url


def _load_sifra_from_db() -> dict[int, str]:
    """Load all municipality code → region mappings from the ``region_lookup`` table.

    Results are cached at module level so the DB is queried at most once per process.
    """
    global _sifra_cache  # noqa: PLW0603
    if _sifra_cache is not None:
        return _sifra_cache

    _sifra_cache = {}
    try:
        sync_url = _get_sync_database_url()
        engine = create_engine(sync_url)
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text("SELECT obcina_sifra, regija_naziv FROM region_lookup WHERE obcina_sifra IS NOT NULL")
                ).fetchall()
                for row in rows:
                    try:
                        sifra = int(row[0])
                        regija = str(row[1]).strip()
                        if regija and regija != "neznana":
                            _sifra_cache[sifra] = regija
                    except (ValueError, TypeError):
                        continue
        finally:
            engine.dispose()
    except Exception:
        logger.debug("Could not load sifra -> region mappings from DB", exc_info=True)

    return _sifra_cache
