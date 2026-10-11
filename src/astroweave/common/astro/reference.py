"""Classical reference tables used to derive chart facts deterministically.

These are fixed rules of Parashari (BPHS) and KP astrology - sign rulership,
dignities, natural friendships, aspects, nakshatras, combustion orbs. Deriving
facts such as "Jupiter rules the 9th and 12th" or "Venus is debilitated" in
code, instead of asking the LLM to work them out, removes a whole class of
arithmetic and lookup mistakes without changing any computed chart value.
"""

from __future__ import annotations

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
SIGN_INDEX = {name: index for index, name in enumerate(SIGNS)}

# Element (tattva) and modality of each sign, Aries..Pisces.
SIGN_ELEMENTS = ["fire", "earth", "air", "water"] * 3
SIGN_MODALITIES = ["movable", "fixed", "dual"] * 4

# Parashari sign lords (the nodes rule no sign).
SIGN_LORDS = [
    "Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
    "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter",
]

PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
CLASSICAL_PLANETS = PLANETS[:7]
NODES = ("Rahu", "Ketu")

# Exaltation sign (debilitation is the opposite sign).
EXALTATION_SIGN = {
    "Sun": 0, "Moon": 1, "Mars": 9, "Mercury": 5, "Jupiter": 3, "Venus": 11, "Saturn": 6,
}
# Moolatrikona: (sign, start degree, end degree) per BPHS.
MOOLATRIKONA = {
    "Sun": (4, 0.0, 20.0),
    "Moon": (1, 3.0, 30.0),
    "Mars": (0, 0.0, 12.0),
    "Mercury": (5, 15.0, 20.0),
    "Jupiter": (8, 0.0, 10.0),
    "Venus": (6, 0.0, 15.0),
    "Saturn": (10, 0.0, 20.0),
}
OWN_SIGNS = {
    "Sun": (4,), "Moon": (3,), "Mars": (0, 7), "Mercury": (2, 5),
    "Jupiter": (8, 11), "Venus": (1, 6), "Saturn": (9, 10),
}
# Naisargika (natural) relationships: friends and enemies; everything else is neutral.
NATURAL_FRIENDS = {
    "Sun": {"Moon", "Mars", "Jupiter"},
    "Moon": {"Sun", "Mercury"},
    "Mars": {"Sun", "Moon", "Jupiter"},
    "Mercury": {"Sun", "Venus"},
    "Jupiter": {"Sun", "Moon", "Mars"},
    "Venus": {"Mercury", "Saturn"},
    "Saturn": {"Mercury", "Venus"},
}
NATURAL_ENEMIES = {
    "Sun": {"Venus", "Saturn"},
    "Moon": set(),
    "Mars": {"Mercury"},
    "Mercury": {"Moon"},
    "Jupiter": {"Mercury", "Venus"},
    "Venus": {"Sun", "Moon"},
    "Saturn": {"Sun", "Moon", "Mars"},
}

# Parashari graha drishti, as house offsets counted from the planet (1 = its own house).
# Every planet aspects the 7th; Mars, Jupiter and Saturn have special aspects. Node
# aspects are disputed in the classics; 5/7/9 is the most common modern practice.
ASPECT_OFFSETS = {
    "Sun": (7,), "Moon": (7,), "Mercury": (7,), "Venus": (7,),
    "Mars": (4, 7, 8), "Jupiter": (5, 7, 9), "Saturn": (3, 7, 10),
    "Rahu": (5, 7, 9), "Ketu": (5, 7, 9),
}

# Combustion orbs from the Sun in degrees (Surya Siddhanta); (direct, retrograde).
COMBUSTION_ORBS = {
    "Moon": (12.0, 12.0),
    "Mars": (17.0, 17.0),
    "Mercury": (14.0, 12.0),
    "Jupiter": (11.0, 11.0),
    "Venus": (10.0, 8.0),
    "Saturn": (15.0, 15.0),
}

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu",
    "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta",
    "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha",
    "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada",
    "Uttara Bhadrapada", "Revati",
]
# Vimshottari order of nakshatra lords, repeating every nine nakshatras from Ashwini.
NAKSHATRA_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
NAKSHATRA_SPAN = 360.0 / 27  # 13 deg 20 min
PADA_SPAN = NAKSHATRA_SPAN / 4  # 3 deg 20 min
