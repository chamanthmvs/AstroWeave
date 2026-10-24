"""Deterministic birth profile: classical facts + plain-language, no LLM.

`build_profile(chart)` reads the computed chart (Moon nakshatra + pada, Moon
rasi, Lagna) and returns the person's fixed classical attributes together with
a plain-language summary a non-astrologer can read. It derives nothing
predictive and invents no prose - every sentence is composed from a canonical
attribute. The individual birth chart modulates these archetypes, which the
caveat states.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .reference import (
    NAKSHATRA_LORDS,
    NAKSHATRA_SPAN,
    NAKSHATRAS,
    PADA_SPAN,
    SIGN_ELEMENTS,
    SIGN_INDEX,
    SIGN_LORDS,
    SIGN_MODALITIES,
    SIGNS,
)
from .profile_reference import (
    ELEMENT_MEANING,
    GANA_MEANING,
    MODALITY_MEANING,
    NADI_MEANING,
    NAKSHATRA_DEITY,
    NAKSHATRA_SYMBOL,
    SIGN_VARNA,
    YONI_ANIMALS,
    YONI_INDEX,
    gana_of,
    nadi_of,
)


def _sign_index(entry: Mapping[str, Any]) -> int:
    if isinstance(entry.get("sign_index"), int):
        return entry["sign_index"] % 12
    return SIGN_INDEX[entry["sign"]]


def build_profile(chart: Mapping[str, Any] | None) -> dict[str, Any]:
    """Build the deterministic profile from a chart-service chart dict."""
    d1 = (chart or {}).get("d1") or {}
    ascendant = d1.get("ascendant")
    planets = {p.get("planet"): p for p in d1.get("planets") or []}
    moon = planets.get("Moon")
    if not ascendant or not moon:
        return {"unavailable": "Moon and ascendant positions are needed to build a profile."}

    moon_sign = _sign_index(moon)
    moon_longitude = moon_sign * 30.0 + float(moon.get("longitude_in_sign", 0.0))
    nak_index = int(moon_longitude // NAKSHATRA_SPAN) % 27          # 0-based
    nak_number = nak_index + 1                                      # 1-based
    pada = int((moon_longitude % NAKSHATRA_SPAN) // PADA_SPAN) + 1
    lagna_sign = _sign_index(ascendant)

    gana = gana_of(nak_number)
    nadi = nadi_of(nak_number)
    yoni = YONI_ANIMALS[YONI_INDEX[nak_index]]
    moon_element = SIGN_ELEMENTS[moon_sign]
    moon_modality = SIGN_MODALITIES[moon_sign]
    lagna_element = SIGN_ELEMENTS[lagna_sign]
    lagna_modality = SIGN_MODALITIES[lagna_sign]

    nakshatra = {
        "name": NAKSHATRAS[nak_index],
        "pada": pada,
        "ruling_planet": NAKSHATRA_LORDS[nak_index % 9],
        "deity": NAKSHATRA_DEITY[nak_index],
        "symbol": NAKSHATRA_SYMBOL[nak_index],
        "gana": gana,
        "yoni": yoni,
        "nadi": nadi,
    }
    rasi = {
        "sign": SIGNS[moon_sign],
        "lord": SIGN_LORDS[moon_sign],
        "element": moon_element,
        "modality": moon_modality,
        "varna": SIGN_VARNA[moon_sign],
    }
    lagna = {
        "sign": SIGNS[lagna_sign],
        "lord": SIGN_LORDS[lagna_sign],
        "element": lagna_element,
        "modality": lagna_modality,
    }

    # Plain-language, each line grounded in an attribute above.
    plain = [
        f"Your Moon is in {rasi['sign']} ({moon_element}), so emotionally you tend to be "
        f"{ELEMENT_MEANING[moon_element]}.",
        f"Your birth star is {nakshatra['name']}, ruled by {nakshatra['ruling_planet']}. Its gana "
        f"({gana}) points to {GANA_MEANING[gana]}.",
        f"Its nadi ({nadi}) suggests {NADI_MEANING[nadi]}.",
        f"Your rising sign (Lagna) is {lagna['sign']} ({lagna_element}, {lagna_modality}), which shapes "
        f"how you come across to others: {ELEMENT_MEANING[lagna_element]}, and {MODALITY_MEANING[lagna_modality]}.",
    ]

    return {
        "summary": {
            "rasi": rasi["sign"],
            "nakshatra": f"{nakshatra['name']} (pada {pada})",
            "lagna": lagna["sign"],
        },
        "nakshatra": nakshatra,
        "rasi": rasi,
        "lagna": lagna,
        "glossary": {
            "gana": GANA_MEANING[gana],
            "nadi": NADI_MEANING[nadi],
            "moon_element": ELEMENT_MEANING[moon_element],
            "moon_modality": MODALITY_MEANING[moon_modality],
            "lagna_element": ELEMENT_MEANING[lagna_element],
            "lagna_modality": MODALITY_MEANING[lagna_modality],
        },
        "in_simple_terms": plain,
        "note": (
            "These are classical archetypes for your Moon star, Moon sign and rising sign. "
            "Your full birth chart - planetary aspects, strengths and current periods - can soften "
            "or sharpen any of them, so treat this as the broad outline, not the whole picture."
        ),
    }
