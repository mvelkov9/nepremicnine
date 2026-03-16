"""Helpers for canonical Slovenian municipality and region labels."""

from __future__ import annotations

import re
import unicodedata

LOWERCASE_WORDS = {
    "in",
    "na",
    "nad",
    "ob",
    "od",
    "pod",
    "pri",
    "proti",
    "v",
    "z",
}

REGION_OVERRIDES = {
    "pomurska": "Pomurska",
    "podravska": "Podravska",
    "koroska": "Koroška",
    "savinjska": "Savinjska",
    "zasavska": "Zasavska",
    "posavska": "Posavska",
    "jugovzhodna slovenija": "Jugovzhodna Slovenija",
    "osrednjeslovenska": "Osrednjeslovenska",
    "gorenjska": "Gorenjska",
    "primorsko notranjska": "Primorsko-notranjska",
    "primorsko-notranjska": "Primorsko-notranjska",
    "goriska": "Goriška",
    "obalno kraska": "Obalno-kraška",
    "obalno-kraska": "Obalno-kraška",
    "neznana": "Neznana",
}

PHRASE_OVERRIDES = {
    "dobrova polhov gradec": "Dobrova - Polhov Gradec",
    "gorenja vas poljane": "Gorenja vas - Poljane",
    "hoce slivnica": "Hoče - Slivnica",
    "hrpelje kozina": "Hrpelje - Kozina",
    "log dragomer": "Log - Dragomer",
    "miren kostanjevica": "Miren - Kostanjevica",
    "mokronog trebelno": "Mokronog - Trebelno",
    "race fram": "Rače - Fram",
    "rence vogrsko": "Renče - Vogrsko",
    "renece vogrsko": "Renče - Vogrsko",
    "sempeter vrtojba": "Šempeter - Vrtojba",
}

WORD_OVERRIDES = {
    "ajdovscina": "Ajdovščina",
    "andraz": "Andraž",
    "apace": "Apače",
    "brezice": "Brežice",
    "crensovci": "Črenšovci",
    "crna": "Črna",
    "crnomelj": "Črnomelj",
    "divaca": "Divača",
    "goriska": "Goriška",
    "gorisnica": "Gorišnica",
    "hodos": "Hodoš",
    "hoce": "Hoče",
    "ivancna": "Ivančna",
    "kidricevo": "Kidričevo",
    "koroska": "Koroška",
    "kraska": "Kraška",
    "krizevci": "Križevci",
    "lasko": "Laško",
    "loska": "Loška",
    "loski": "Loški",
    "mezica": "Mežica",
    "miklavz": "Miklavž",
    "ormoz": "Ormož",
    "pec": "Peč",
    "podcetrtek": "Podčetrtek",
    "race": "Rače",
    "razkrizje": "Razkrižje",
    "renece": "Renče",
    "rogaska": "Rogaška",
    "scavnici": "Ščavnici",
    "sezana": "Sežana",
    "semic": "Semič",
    "sencur": "Šenčur",
    "sentilj": "Šentilj",
    "sentjernej": "Šentjernej",
    "sentjur": "Šentjur",
    "sentrupert": "Šentrupert",
    "sempeter": "Šempeter",
    "skocjan": "Škocjan",
    "skofja": "Škofja",
    "skofljica": "Škofljica",
    "smarje": "Šmarje",
    "smarjeske": "Šmarješke",
    "smartno": "Šmartno",
    "sodrazica": "Sodražica",
    "sol": "Solčava",
    "solcava": "Solčava",
    "sostanj": "Šoštanj",
    "starse": "Starše",
    "store": "Štore",
    "sv": "Sv.",
    "sveta": "Sveta",
    "sveti": "Sveti",
    "turnisce": "Turnišče",
    "zalec": "Žalec",
    "zavrc": "Zavrč",
    "zelezniki": "Železniki",
    "zetale": "Žetale",
    "ziri": "Žiri",
    "zirovnica": "Žirovnica",
    "zrece": "Zreče",
    "zuzemberk": "Žužemberk",
}


def normalize_label(value: object | None) -> str:
    if value is None:
        return ""

    text = " ".join(str(value).strip().split())
    if not text:
        return ""

    folded = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(char for char in folded if not unicodedata.combining(char))
    ascii_text = ascii_text.lower()
    ascii_text = re.sub(r"[^a-z0-9]+", " ", ascii_text)
    return re.sub(r"\s+", " ", ascii_text).strip()


def labels_match(left: object | None, right: object | None) -> bool:
    left_normalized = normalize_label(left)
    right_normalized = normalize_label(right)
    return bool(left_normalized and right_normalized and left_normalized == right_normalized)


def format_region_label(value: object | None) -> str | None:
    normalized = normalize_label(value)
    if not normalized:
        return None
    return REGION_OVERRIDES.get(normalized, _titleize_plain(str(value)))


def format_municipality_label(value: object | None) -> str | None:
    if value is None:
        return None

    text = " ".join(str(value).strip().split())
    normalized = normalize_label(text)
    if not normalized:
        return None

    if normalized in PHRASE_OVERRIDES:
        return PHRASE_OVERRIDES[normalized]

    tokens = re.split(r"([\\s\\-/]+)", text.lower())
    formatted: list[str] = []
    word_index = 0

    for token in tokens:
        if token == "":
            continue
        if re.fullmatch(r"[\\s\\-/]+", token):
            formatted.append(token)
            continue

        key = normalize_label(token).replace(" ", "")
        if not key:
            formatted.append(token)
            continue

        if key in WORD_OVERRIDES:
            replacement = WORD_OVERRIDES[key]
        elif key in LOWERCASE_WORDS and word_index > 0:
            replacement = key
        else:
            replacement = token[:1].upper() + token[1:]

        formatted.append(replacement)
        word_index += 1

    label = "".join(formatted)
    label = re.sub(r"\s*-\s*", " - ", label)
    return re.sub(r"\s+", " ", label).strip()


def _titleize_plain(value: str) -> str:
    text = " ".join(value.strip().split())
    if not text:
        return value
    return " ".join(part[:1].upper() + part[1:].lower() for part in text.split(" "))
