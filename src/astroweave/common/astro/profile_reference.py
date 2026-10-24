"""Canonical classical attributes for a deterministic birth profile.

Everything here is a fixed lookup from the person's Moon nakshatra, Moon rasi
and Lagna - ruling planet, deity, symbol, gana, yoni, nadi, element, modality,
varna - plus short, plain-language meanings grounded in those attributes. No
prediction and no LLM: these are classical classifications, and the individual
birth chart modulates them (stated in the profile's caveat).

Sources are standard Jyotish references (BPHS and the common nakshatra tables);
the gana / nadi / yoni groupings match those validated in the matching tests.
"""

from __future__ import annotations

# North-Indian / Sanskrit nakshatra names, index 0 = Ashwini .. 26 = Revati.
NAKSHATRA_NAME = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu",
    "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta",
    "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha",
    "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada",
    "Uttara Bhadrapada", "Revati",
]
# South-Indian (Tamil) names in common use, same index order.
NAKSHATRA_SOUTH_NAME = [
    "Aswini", "Bharani", "Karthigai", "Rohini", "Mirugasirisham", "Thiruvathirai",
    "Punarpoosam", "Poosam", "Ayilyam", "Magam", "Pooram", "Uthiram", "Hastham",
    "Chithirai", "Swathi", "Visakam", "Anusham", "Kettai", "Moolam", "Pooradam",
    "Uthiradam", "Thiruvonam", "Avittam", "Sadayam", "Pooratathi", "Uthiratathi",
    "Revathi",
]
# Short classical theme (what the nakshatra chiefly represents), grounded in its
# traditional symbol and deity - not a personality prediction.
NAKSHATRA_THEME = [
    "swift action, healing and fresh starts",
    "restraint, bearing and transformation",
    "sharp purification and fire",
    "growth, fertility and nourishment",
    "searching, curiosity and gentle quest",
    "storm, upheaval and renewal",
    "return, renewal and safe repetition",
    "nourishment, support and care",
    "entwining insight and hidden depth",
    "ancestry, throne and legacy",
    "pleasure, rest and union",
    "patronage, friendship and generous order",
    "skill of the hands and craft",
    "brilliance, design and dazzling form",
    "independence, movement and balance",
    "focused purpose and determination",
    "devotion and cooperative success",
    "seniority, protection and hard-won authority",
    "roots, inquiry and dissolution",
    "invincibility and early momentum",
    "lasting victory and integrity",
    "listening, learning and connection",
    "rhythm, wealth and music",
    "healing, secrecy and the hundred physicians",
    "intensity, idealism and fiery vision",
    "depth, calm wisdom and deep waters",
    "completion and safe passage",
]
# Classical meaning / translation of each nakshatra name, same index order.
NAKSHATRA_MEANING = [
    "the horse-woman; swift healers", "the bearer; she who carries", "the cutter; the flame",
    "the red, growing one", "the deer's head; the search", "the moist one; the storm",
    "the return of the light", "the nourisher", "the embrace; the coiled one",
    "the mighty; the throne", "the former red one", "the latter red one", "the hand",
    "the brilliant; the bright jewel", "the self-going; the sword", "the forked, two-branched",
    "the follower of Radha", "the eldest", "the root", "the former invincible one",
    "the latter invincible one", "the ear; listening", "the wealthiest; the drum",
    "the hundred healers", "the former blessed feet", "the latter blessed feet",
    "the prosperous one",
]

# Vimshottari dasha lord by nakshatra (the 9-planet cycle, repeated three times).
_VIMSHOTTARI_CYCLE = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]

# The twelve rasis (zodiac signs) with standard classical attributes. Exaltation /
# debilitation follow BPHS (e.g. Sun exalts in Aries, is debilitated in Libra).
RASI = [
    {"number": 1, "name": "Aries", "sanskrit": "Mesha", "symbol": "Ram", "lord": "Mars",
     "element": "Fire", "modality": "Movable", "polarity": "Masculine",
     "exalted": "Sun", "debilitated": "Saturn", "body_part": "Head",
     "keynote": "pioneering, assertive and quick to begin"},
    {"number": 2, "name": "Taurus", "sanskrit": "Vrishabha", "symbol": "Bull", "lord": "Venus",
     "element": "Earth", "modality": "Fixed", "polarity": "Feminine",
     "exalted": "Moon", "debilitated": None, "body_part": "Face and neck",
     "keynote": "steady, sensual and resource-building"},
    {"number": 3, "name": "Gemini", "sanskrit": "Mithuna", "symbol": "Twins", "lord": "Mercury",
     "element": "Air", "modality": "Dual", "polarity": "Masculine",
     "exalted": None, "debilitated": None, "body_part": "Shoulders and arms",
     "keynote": "curious, communicative and versatile"},
    {"number": 4, "name": "Cancer", "sanskrit": "Karka", "symbol": "Crab", "lord": "Moon",
     "element": "Water", "modality": "Movable", "polarity": "Feminine",
     "exalted": "Jupiter", "debilitated": "Mars", "body_part": "Chest and heart",
     "keynote": "nurturing, protective and feeling"},
    {"number": 5, "name": "Leo", "sanskrit": "Simha", "symbol": "Lion", "lord": "Sun",
     "element": "Fire", "modality": "Fixed", "polarity": "Masculine",
     "exalted": None, "debilitated": None, "body_part": "Stomach and upper abdomen",
     "keynote": "confident, dignified and expressive"},
    {"number": 6, "name": "Virgo", "sanskrit": "Kanya", "symbol": "Maiden", "lord": "Mercury",
     "element": "Earth", "modality": "Dual", "polarity": "Feminine",
     "exalted": "Mercury", "debilitated": "Venus", "body_part": "Waist and abdomen",
     "keynote": "analytical, precise and service-minded"},
    {"number": 7, "name": "Libra", "sanskrit": "Tula", "symbol": "Scales", "lord": "Venus",
     "element": "Air", "modality": "Movable", "polarity": "Masculine",
     "exalted": "Saturn", "debilitated": "Sun", "body_part": "Lower abdomen and kidneys",
     "keynote": "balancing, relational and fair-minded"},
    {"number": 8, "name": "Scorpio", "sanskrit": "Vrishchika", "symbol": "Scorpion", "lord": "Mars",
     "element": "Water", "modality": "Fixed", "polarity": "Feminine",
     "exalted": None, "debilitated": "Moon", "body_part": "Pelvis and genitals",
     "keynote": "intense, probing and transformative"},
    {"number": 9, "name": "Sagittarius", "sanskrit": "Dhanu", "symbol": "Archer", "lord": "Jupiter",
     "element": "Fire", "modality": "Dual", "polarity": "Masculine",
     "exalted": None, "debilitated": None, "body_part": "Hips and thighs",
     "keynote": "philosophical, optimistic and seeking"},
    {"number": 10, "name": "Capricorn", "sanskrit": "Makara", "symbol": "Sea-goat (crocodile)", "lord": "Saturn",
     "element": "Earth", "modality": "Movable", "polarity": "Feminine",
     "exalted": "Mars", "debilitated": "Jupiter", "body_part": "Knees",
     "keynote": "disciplined, ambitious and enduring"},
    {"number": 11, "name": "Aquarius", "sanskrit": "Kumbha", "symbol": "Water-bearer", "lord": "Saturn",
     "element": "Air", "modality": "Fixed", "polarity": "Masculine",
     "exalted": None, "debilitated": None, "body_part": "Calves and ankles",
     "keynote": "independent, humanitarian and inventive"},
    {"number": 12, "name": "Pisces", "sanskrit": "Meena", "symbol": "Fishes", "lord": "Jupiter",
     "element": "Water", "modality": "Dual", "polarity": "Feminine",
     "exalted": "Venus", "debilitated": "Mercury", "body_part": "Feet",
     "keynote": "compassionate, imaginative and surrendering"},
]


def rasi_catalog() -> list[dict]:
    """The twelve rasis with their canonical attributes (a copy, for the atlas)."""
    return [dict(sign) for sign in RASI]


def vimshottari_lord(nakshatra_number: int) -> str:
    """Ruling (dasha) planet for a nakshatra numbered 1..27."""
    return _VIMSHOTTARI_CYCLE[(nakshatra_number - 1) % 9]


# Nakshatra deity and symbol, index 0 = Ashwini .. 26 = Revati.
NAKSHATRA_DEITY = [
    "Ashwini Kumaras", "Yama", "Agni", "Brahma (Prajapati)", "Soma (Chandra)", "Rudra",
    "Aditi", "Brihaspati", "Nagas", "Pitris (ancestors)", "Bhaga", "Aryaman", "Savitar",
    "Tvashtar / Vishwakarma", "Vayu", "Indra and Agni", "Mitra", "Indra", "Nirriti",
    "Apas (the waters)", "Vishvadevas", "Vishnu", "The Vasus", "Varuna", "Aja Ekapada",
    "Ahir Budhnya", "Pushan",
]
NAKSHATRA_SYMBOL = [
    "horse's head", "yoni (female organ)", "razor / flame", "ox-cart / chariot",
    "deer's head", "teardrop / gem", "bow and quiver", "cow's udder / flower",
    "coiled serpent", "royal throne", "front legs of a cot", "back legs of a cot",
    "hand / fist", "bright jewel / pearl", "young shoot / coral", "triumphal arch",
    "lotus", "earring / umbrella", "bunch of roots", "fan / winnowing basket",
    "elephant tusk / planks", "ear / three footprints", "drum (damaru)",
    "empty circle / 100 flowers", "front of a funeral cot", "back of a funeral cot",
    "fish / drum",
]
# Yoni (animal) per nakshatra: index into YONI_ANIMALS (matches PyJHora's mapping).
YONI_INDEX = [0, 1, 2, 3, 3, 4, 5, 2, 5, 6, 6, 7, 8, 9, 8, 9, 10, 10, 4, 11, 12, 11, 13, 0, 13, 7, 1]
YONI_ANIMALS = ["Horse", "Elephant", "Sheep", "Serpent", "Dog", "Cat", "Rat", "Cow",
                "Buffalo", "Tiger", "Deer", "Monkey", "Mongoose", "Lion"]

# Gana and Nadi groupings (nakshatra numbers 1..27) - the same classical sets the
# matching validation uses.
GANA_DEVA = {1, 5, 7, 8, 13, 15, 17, 22, 27}
GANA_MANUSHYA = {2, 4, 6, 11, 12, 20, 21, 25, 26}
NADI_VATA = {1, 6, 7, 12, 13, 18, 19, 24, 25}      # Aadi
NADI_PITTA = {2, 5, 8, 11, 14, 17, 20, 23, 26}     # Madhya


def gana_of(nakshatra_number: int) -> str:
    if nakshatra_number in GANA_DEVA:
        return "Deva"
    if nakshatra_number in GANA_MANUSHYA:
        return "Manushya"
    return "Rakshasa"


def nadi_of(nakshatra_number: int) -> str:
    if nakshatra_number in NADI_VATA:
        return "Vata"
    if nakshatra_number in NADI_PITTA:
        return "Pitta"
    return "Kapha"


# Varna by Moon sign (rasi index 0 = Aries). Water=Brahmin, Fire=Kshatriya,
# Earth=Vaishya, Air=Shudra.
SIGN_VARNA = [
    "Kshatriya", "Vaishya", "Shudra", "Brahmin", "Kshatriya", "Vaishya",
    "Shudra", "Brahmin", "Kshatriya", "Vaishya", "Shudra", "Brahmin",
]

# Plain-language meanings, grounded in the attribute (not personality guesswork).
GANA_MEANING = {
    "Deva": "a gentle, generous, principled temperament",
    "Manushya": "a balanced, practical, human mix of drives",
    "Rakshasa": "a strong-willed, intense, determined temperament",
}
NADI_MEANING = {
    "Vata": "an active, quick, creative constitution that can run restless",
    "Pitta": "a driven, sharp, warm constitution that can run intense",
    "Kapha": "a calm, steady, nurturing constitution that resists being rushed",
}
ELEMENT_MEANING = {
    "fire": "energetic, assertive and inspired",
    "earth": "grounded, practical and reliable",
    "air": "communicative, social and intellectual",
    "water": "emotional, intuitive and caring",
}
MODALITY_MEANING = {
    "movable": "initiating and dynamic, comfortable with change",
    "fixed": "steady and persistent, slow to change course",
    "dual": "adaptable, flexible and versatile",
}

_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]


def _degree_label(total_degrees: float) -> str:
    """Format a sidereal longitude as 'Sign dd°mm'' (e.g. 'Aries 13°20'')."""
    total_degrees %= 360.0
    sign = _SIGNS[int(total_degrees // 30)]
    within = total_degrees % 30
    degrees = int(within)
    minutes = round((within - degrees) * 60)
    if minutes == 60:  # rounding carry
        degrees, minutes = degrees + 1, 0
    return f"{sign} {degrees}°{minutes:02d}'"


def nakshatra_catalog() -> list[dict]:
    """The 27 nakshatras with their canonical attributes, for the reference atlas.

    Deterministic and classical: names (North/Sanskrit + South/Tamil), symbol,
    deity, ruling (Vimshottari) planet, gana, yoni, nadi, the short theme, and
    the sidereal span (each nakshatra is 13°20'). No prediction.
    """
    span = 40.0 / 3.0  # 13 degrees 20 minutes
    catalog = []
    for index in range(27):
        number = index + 1
        catalog.append({
            "number": number,
            "name": NAKSHATRA_NAME[index],
            "south_name": NAKSHATRA_SOUTH_NAME[index],
            "meaning": NAKSHATRA_MEANING[index],
            "symbol": NAKSHATRA_SYMBOL[index],
            "deity": NAKSHATRA_DEITY[index],
            "ruling_planet": vimshottari_lord(number),
            "gana": gana_of(number),
            "yoni": YONI_ANIMALS[YONI_INDEX[index]],
            "nadi": nadi_of(number),
            "theme": NAKSHATRA_THEME[index],
            "span": {
                "start": _degree_label(index * span),
                "end": _degree_label(number * span),
            },
        })
    return catalog
