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
