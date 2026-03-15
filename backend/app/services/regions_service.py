"""Region lookup service: municipality → statistical region, with fallback data."""

import unicodedata


# ── Fallback: municipality → region mapping (lowercase, no diacritics) ────────
_FALLBACK_BY_REGION = {
    "Pomurska": [
        "apace", "beltinci", "cankova", "crensovci", "dobrovnik",
        "gornja radgona", "gornji petrovci", "grad", "hodos", "kobilje",
        "krizevci", "kuzma", "lendava", "ljutomer", "moravske toplice",
        "murska sobota", "odranci", "puconci", "radenci", "razkrizje",
        "rogasovci", "salovci", "sveti jurij ob scavnici", "tisina",
        "turnisce", "velika polana", "verzej",
        "sveti andraz v slov. goricah", "sveti jurij v slov. goricah",
    ],
    "Podravska": [
        "benedikt", "cerkvenjak", "cirkulane", "destrnik", "dornava",
        "duplek", "gorisnica", "hajdina", "hoce - slivnica", "hoce-slivnica",
        "jursinci", "kidricevo", "kungota", "lenart", "lovrenc na pohorju",
        "majsperk", "makole", "maribor", "markovci",
        "miklavz na dravskem polju", "oplotnica",
        "ormoz", "pesnica", "podlehnik", "poljcane", "ptuj",
        "race - fram", "race-fram",
        "ruse", "selnica ob dravi", "slovenska bistrica",
        "sredisce ob dravi", "starse", "sveta ana",
        "sveta trojica v slovenskih goricah",
        "sv. trojica v slov. goricah",
        "sveti andraz v slovenskih goricah",
        "sveti jurij v slovenskih goricah", "sveti tomaz",
        "sentilj", "trnovska vas", "videm", "zavrc", "zetale",
    ],
    "Koroska": [
        "crna na koroskem", "dravograd", "mezica", "mislinja", "muta",
        "podvelka", "prevalje", "radlje ob dravi",
        "ravne na koroskem", "ribnica na pohorju", "slovenj gradec",
        "vuzenica",
    ],
    "Savinjska": [
        "braslovce", "celje", "dobje", "dobrna", "gornji grad",
        "kozje", "lasko", "ljubno", "luce", "mozirje", "nazarje",
        "podcetrtek", "polzela", "prebold", "recica ob savinji",
        "rogaska slatina", "rogatec",
        "sentjur", "smarje pri jelsah", "smartno ob paki",
        "slovenske konjice", "sol pri savinji", "sol",
        "solcava", "sostanj", "store", "tabor", "velenje", "vitanje",
        "vojnik", "vransko", "zalec", "zrece",
    ],
    "Zasavska": [
        "hrastnik", "trbovlje", "zagorje ob savi",
    ],
    "Posavska": [
        "brezice", "kostanjevica na krki", "krsko", "radece",
        "sevnica", "bistrica ob sotli",
    ],
    "Jugovzhodna Slovenija": [
        "crnomelj", "dolenjske toplice", "kocevje", "kostel",
        "loski potok", "metlika", "mirna", "mirna pec",
        "mokronog - trebelno", "mokronog-trebelno", "novo mesto",
        "osilnica", "ribnica", "semic", "skocjan",
        "smarjeske toplice", "straza", "sodrazica", "sucna vas",
        "sentjernej", "sentrupert", "trebnje", "zuzemberk",
    ],
    "Osrednjeslovenska": [
        "borovnica", "brezovica", "dobrepolje", "dobrova - polhov gradec",
        "dobrova-polhov gradec", "dol pri ljubljani", "domzale",
        "grosuplje", "horjul", "ig", "ivancna gorica", "kamnik",
        "komenda", "litija", "ljubljana", "log - dragomer", "log-dragomer",
        "logatec", "lukovica", "medvode", "menges", "moravce",
        "skofljica", "smartno pri litiji", "trzin", "velike lasce",
        "vodice", "vrhnika",
    ],
    "Gorenjska": [
        "bled", "bohinj", "cerklje na gorenjskem", "gorenja vas - poljane",
        "gorenja vas-poljane", "gorje", "jesenice", "jezersko", "kranj",
        "kranjska gora", "naklo", "preddvor", "radovljica", "sencur",
        "skofja loka", "trzic", "zelezniki", "ziri", "zirovnica",
    ],
    "Primorsko-notranjska": [
        "bloke", "cerknica", "ilirska bistrica", "loska dolina",
        "pivka", "postojna",
    ],
    "Goriska": [
        "ajdovscina", "bovec", "brda", "cerkno", "idrija",
        "kanal ob soci", "kanal", "kobarid", "miren - kostanjevica",
        "miren-kostanjevica", "nova gorica",
        "rence-vogrsko", "renece - vogrsko", "renece-vogrsko",
        "sempeter - vrtojba", "sempeter-vrtojba",
        "tolmin", "vipava",
    ],
    "Obalno-kraska": [
        "ankaran", "divaca", "hrpelje - kozina", "hrpelje-kozina",
        "izola", "komen", "koper", "piran", "sezana",
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
