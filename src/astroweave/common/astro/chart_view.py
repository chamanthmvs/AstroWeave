"""Turn the chart service's raw output into a compact, analysis-ready view.

Specialists used to receive the chart service JSON verbatim (~30k characters:
every varga, 81 dasha rows, boilerplate yoga text) and had to work out house
placements, lordships, dignities, aspects and KP significators themselves -
exactly the mechanical steps where language models slip. This module derives
those facts in code and keeps the sections relevant to the specialist's domain
and methodology.

It never alters a computed value: every position, date, strength and bindu
comes from the chart service unchanged. The view only labels, cross-references
and selects, so the specialist spends its effort on judgment, not arithmetic.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta
from typing import Any

from .reference import (
    ASPECT_OFFSETS,
    CLASSICAL_PLANETS,
    COMBUSTION_ORBS,
    EXALTATION_SIGN,
    MOOLATRIKONA,
    NAKSHATRA_LORDS,
    NAKSHATRA_SPAN,
    NAKSHATRAS,
    NATURAL_ENEMIES,
    NATURAL_FRIENDS,
    NODES,
    OWN_SIGNS,
    PADA_SPAN,
    PLANETS,
    SIGN_ELEMENTS,
    SIGN_INDEX,
    SIGN_LORDS,
    SIGN_MODALITIES,
    SIGNS,
)

# Divisional charts each domain is judged from (D1 is always included).
DOMAIN_VARGAS: dict[str, tuple[str, ...]] = {
    "career": ("D9", "D10", "D24"),
    "finance": ("D2", "D4", "D9", "D10"),
    "love": ("D9", "D7"),
    "sports": ("D3", "D9", "D10", "D30"),
    # Whole-person readings plus the life areas it covers (siblings, property,
    # children, career overview, parents, education).
    "general": ("D9", "D3", "D4", "D7", "D10", "D12", "D24"),
}
_DEFAULT_VARGAS = ("D9", "D10")
_YEAR_DAYS = 365.2425


def build_chart_view(
    chart: Mapping[str, Any] | None,
    domain: str | None = None,
    methodology: str | None = None,
) -> dict[str, Any]:
    """Build the chart view handed to one specialist.

    `methodology` is "vedic", "kp" or "both"; anything else is treated as
    "both". A KP-only view leaves out the Parashari-only sections (vargas,
    yogas, ashtakavarga, shadbala) that KP does not use.
    """
    chart = chart or {}
    d1 = chart.get("d1") or {}
    ascendant = d1.get("ascendant")
    raw_planets = {p["planet"]: p for p in d1.get("planets") or [] if p.get("planet") in PLANETS}
    if not ascendant or not {"Sun", "Moon"} <= raw_planets.keys():
        return {"unavailable": "Natal planetary positions were not provided, so no chart-based judgment is possible."}

    methodology = (methodology or "both").lower()
    if methodology not in ("vedic", "kp", "both"):
        methodology = "both"
    parashari = methodology in ("vedic", "both")

    lagna = _sign_index(ascendant)
    as_of = _as_of(chart)
    varga_charts = chart.get("divisional_charts") or {}
    d9_signs = _varga_sign_map(varga_charts.get("D9"))
    sav_by_sign = _sav_by_sign(chart.get("ashtakavarga"))

    planets = _planet_table(raw_planets, lagna, d9_signs, chart.get("shadbala") or {})
    houses = _house_table(planets, lagna, sav_by_sign)
    view: dict[str, Any] = {
        "meta": _meta(chart, domain, methodology, as_of),
        "summary": _summary(ascendant, lagna, planets, varga_charts),
        "planets": planets,
        "houses": houses,
    }

    if parashari:
        if bhava_shifts := _bhava_shifts(chart.get("bhava_chart"), planets):
            view["bhava_chalit_shifts"] = bhava_shifts
        selected = DOMAIN_VARGAS.get(domain or "", _DEFAULT_VARGAS)
        vargas = {label: _varga_view(varga_charts[label]) for label in selected if varga_charts.get(label)}
        if vargas:
            view["divisional_charts"] = vargas
        if yogas := chart.get("yogas"):
            view["yogas"] = [
                {"name": yoga.get("name"), "condition": yoga.get("description")} for yoga in yogas
            ]
        if bav := _bav_by_house(chart.get("ashtakavarga"), lagna):
            view["bhinna_ashtakavarga_by_house"] = bav

    if dasha := _dasha_view(chart.get("dasha_bhukti"), chart.get("current_dasha"), as_of):
        view["dasha"] = dasha
    if transits := _transit_view(chart.get("transits"), lagna, planets, chart.get("ashtakavarga")):
        view["transits"] = transits
    if methodology in ("kp", "both") and (kp := _kp_view(chart.get("kp"))):
        view["kp"] = kp
    return view


# --- primitives ----------------------------------------------------------


def _sign_index(entry: Mapping[str, Any]) -> int:
    if isinstance(entry.get("sign_index"), int):
        return entry["sign_index"] % 12
    return SIGN_INDEX[entry["sign"]]


def _absolute_longitude(entry: Mapping[str, Any]) -> float:
    return _sign_index(entry) * 30.0 + float(entry.get("longitude_in_sign", 0.0))


def _house_from(sign: int, reference_sign: int) -> int:
    return (sign - reference_sign) % 12 + 1


def _nakshatra(longitude: float) -> tuple[str, int, str]:
    index = int(longitude // NAKSHATRA_SPAN) % 27
    pada = int((longitude % NAKSHATRA_SPAN) // PADA_SPAN) + 1
    return NAKSHATRAS[index], pada, NAKSHATRA_LORDS[index % 9]


def _angular_distance(first: float, second: float) -> float:
    difference = abs(first - second) % 360.0
    return min(difference, 360.0 - difference)


def dignity(planet: str, sign: int, degree: float | None = None) -> str:
    """Classical dignity of a planet in a sign (degree refines moolatrikona)."""
    if planet in NODES:
        return f"node (dispositor {SIGN_LORDS[sign]})"
    exaltation = EXALTATION_SIGN[planet]
    moolatrikona_sign, mt_start, mt_end = MOOLATRIKONA[planet]
    in_moolatrikona = sign == moolatrikona_sign and (degree is None or mt_start <= degree < mt_end)
    if sign == exaltation:
        # Moon (Taurus) and Mercury (Virgo) share their exaltation sign with moolatrikona.
        if degree is not None and in_moolatrikona and planet in ("Moon", "Mercury"):
            return "moolatrikona"
        if planet == "Mercury" and degree is not None and degree >= 20.0:
            return "own sign"
        return "exalted"
    if sign == (exaltation + 6) % 12:
        return "debilitated"
    if in_moolatrikona:
        return "moolatrikona"
    if sign in OWN_SIGNS[planet]:
        return "own sign"
    lord = SIGN_LORDS[sign]
    if lord in NATURAL_FRIENDS[planet]:
        return "friendly sign"
    if lord in NATURAL_ENEMIES[planet]:
        return "enemy sign"
    return "neutral sign"


def _aspected_houses(planet: str, house: int) -> list[int]:
    return sorted((house + offset - 2) % 12 + 1 for offset in ASPECT_OFFSETS[planet])


def _ruled_houses(planet: str, lagna: int) -> list[int]:
    return [house for house in range(1, 13) if SIGN_LORDS[(lagna + house - 1) % 12] == planet]


# --- natal (D1) ----------------------------------------------------------


def _planet_table(
    raw: Mapping[str, Mapping[str, Any]],
    lagna: int,
    d9_signs: Mapping[str, int],
    shadbala: Mapping[str, Any],
) -> list[dict[str, Any]]:
    sun_longitude = _absolute_longitude(raw["Sun"])
    house_of = {name: _house_from(_sign_index(entry), lagna) for name, entry in raw.items()}
    aspects_of = {name: _aspected_houses(name, house) for name, house in house_of.items()}

    table = []
    for name in PLANETS:
        entry = raw.get(name)
        if entry is None:
            continue
        sign = _sign_index(entry)
        degree = float(entry.get("longitude_in_sign", 0.0))
        longitude = _absolute_longitude(entry)
        retrograde = bool(entry.get("retrograde", False))
        nakshatra, pada, nakshatra_lord = _nakshatra(longitude)
        row: dict[str, Any] = {
            "planet": name,
            "sign": SIGNS[sign],
            "degree": round(degree, 2),
            "house": house_of[name],
            "nakshatra": nakshatra,
            "pada": pada,
            "nakshatra_lord": nakshatra_lord,
            "rules_houses": _ruled_houses(name, lagna),
            "dignity": dignity(name, sign, degree),
            "retrograde": retrograde,
        }
        if name in COMBUSTION_ORBS:
            orb = COMBUSTION_ORBS[name][1 if retrograde else 0]
            row["combust"] = _angular_distance(longitude, sun_longitude) <= orb
        if name in d9_signs:
            row["vargottama"] = d9_signs[name] == sign
        row["conjunct_with"] = [
            other for other in PLANETS
            if other != name and other in raw and _sign_index(raw[other]) == sign
        ]
        row["aspects_houses"] = aspects_of[name]
        row["aspected_by"] = sorted(
            other for other, houses in aspects_of.items()
            if other != name and house_of[name] in houses
        )
        strength = shadbala.get(name)
        if isinstance(strength, Mapping) and "strength_ratio" in strength:
            row["shadbala_ratio"] = round(float(strength["strength_ratio"]), 2)
        table.append(row)
    return table


def _house_table(
    planets: list[dict[str, Any]], lagna: int, sav_by_sign: list[int] | None
) -> list[dict[str, Any]]:
    by_name = {row["planet"]: row for row in planets}
    table = []
    for house in range(1, 13):
        sign = (lagna + house - 1) % 12
        lord = SIGN_LORDS[sign]
        row: dict[str, Any] = {
            "house": house,
            "sign": SIGNS[sign],
            "lord": lord,
            "lord_in_house": by_name[lord]["house"] if lord in by_name else None,
            "lord_dignity": by_name[lord]["dignity"] if lord in by_name else None,
            "occupants": [row["planet"] for row in planets if row["house"] == house],
            "aspected_by": [row["planet"] for row in planets if house in row["aspects_houses"]],
        }
        if sav_by_sign is not None:
            row["sarvashtakavarga_bindus"] = sav_by_sign[sign]
        table.append(row)
    return table


def _summary(
    ascendant: Mapping[str, Any],
    lagna: int,
    planets: list[dict[str, Any]],
    varga_charts: Mapping[str, Any],
) -> dict[str, Any]:
    by_name = {row["planet"]: row for row in planets}
    lagna_lord = SIGN_LORDS[lagna]
    lagna_longitude = _absolute_longitude(ascendant)
    nakshatra, pada, nakshatra_lord = _nakshatra(lagna_longitude)
    moon = by_name["Moon"]
    summary: dict[str, Any] = {
        "lagna": SIGNS[lagna],
        "lagna_degree": round(float(ascendant.get("longitude_in_sign", 0.0)), 2),
        "lagna_nakshatra": f"{nakshatra} pada {pada} (lord {nakshatra_lord})",
        "lagna_lord": lagna_lord,
        "lagna_lord_house": by_name[lagna_lord]["house"],
        "lagna_lord_dignity": by_name[lagna_lord]["dignity"],
        "moon_sign": moon["sign"],
        "janma_nakshatra": f"{moon['nakshatra']} pada {moon['pada']} (lord {moon['nakshatra_lord']})",
        "sun_sign": by_name["Sun"]["sign"],
        "retrograde": [row["planet"] for row in planets if row["retrograde"] and row["planet"] not in NODES],
        "combust": [row["planet"] for row in planets if row.get("combust")],
        "vargottama": [row["planet"] for row in planets if row.get("vargottama")],
    }
    # Element and modality balance over the lagna and the seven classical planets.
    signs = [lagna] + [SIGN_INDEX[row["sign"]] for row in planets if row["planet"] in CLASSICAL_PLANETS]
    summary["element_balance"] = {
        element: sum(SIGN_ELEMENTS[sign] == element for sign in signs) for element in ("fire", "earth", "air", "water")
    }
    summary["modality_balance"] = {
        modality: sum(SIGN_MODALITIES[sign] == modality for sign in signs) for modality in ("movable", "fixed", "dual")
    }
    d9 = varga_charts.get("D9") or {}
    if d9.get("ascendant"):
        summary["lagna_vargottama"] = _sign_index(d9["ascendant"]) == lagna
    return summary


def _bhava_shifts(bhava_chart: Any, planets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Planets whose equal-house (bhava chalit) house differs from their sign house."""
    if not isinstance(bhava_chart, list) or len(bhava_chart) != 12:
        return []
    sign_house = {row["planet"]: row["house"] for row in planets}
    shifts = []
    for bhava, entry in enumerate(bhava_chart, start=1):
        for name in entry.get("planets") or []:
            if name in sign_house and sign_house[name] != bhava:
                shifts.append({"planet": name, "sign_house": sign_house[name], "bhava_house": bhava})
    return shifts


# --- divisional charts and ashtakavarga ---------------------------------


def _varga_sign_map(varga: Any) -> dict[str, int]:
    if not isinstance(varga, Mapping):
        return {}
    return {p["planet"]: _sign_index(p) for p in varga.get("planets") or [] if p.get("planet") in PLANETS}


def _varga_view(varga: Mapping[str, Any]) -> dict[str, Any]:
    lagna = _sign_index(varga["ascendant"])
    rows = []
    for entry in varga.get("planets") or []:
        name = entry.get("planet")
        if name not in PLANETS:
            continue
        sign = _sign_index(entry)
        rows.append({
            "planet": name,
            "sign": SIGNS[sign],
            "house": _house_from(sign, lagna),
            # Degrees inside a varga are not meaningful for moolatrikona ranges.
            "dignity": dignity(name, sign),
        })
    return {"ascendant": SIGNS[lagna], "planets": rows}


def _sav_by_sign(ashtakavarga: Any) -> list[int] | None:
    if not isinstance(ashtakavarga, Mapping):
        return None
    totals = ashtakavarga.get("samudhaya")
    if isinstance(totals, Mapping):
        return [int(totals.get(sign, 0)) for sign in SIGNS]
    if isinstance(totals, list) and len(totals) == 12:
        return [int(value) for value in totals]
    return None


def _bav_sign_table(ashtakavarga: Any) -> dict[str, list[int]]:
    if not isinstance(ashtakavarga, Mapping):
        return {}
    table = {}
    for planet, row in (ashtakavarga.get("binna") or {}).items():
        if planet not in CLASSICAL_PLANETS:
            continue
        if isinstance(row, Mapping):
            table[planet] = [int(row.get(sign, 0)) for sign in SIGNS]
        elif isinstance(row, list) and len(row) == 12:
            table[planet] = [int(value) for value in row]
    return table


def _bav_by_house(ashtakavarga: Any, lagna: int) -> dict[str, list[int]]:
    """Bhinna ashtakavarga per planet, re-ordered as houses 1..12 from the lagna."""
    return {
        planet: [row[(lagna + house) % 12] for house in range(12)]
        for planet, row in _bav_sign_table(ashtakavarga).items()
    }


# --- timing --------------------------------------------------------------


def _as_of(chart: Mapping[str, Any]) -> date:
    for section in ("current_dasha", "transits"):
        stamp = (chart.get(section) or {}).get("as_of")
        if isinstance(stamp, str):
            try:
                return datetime.strptime(stamp[:10], "%Y-%m-%d").date()
            except ValueError:
                continue
    return date.today()


def _status(start: date, end: date, today: date) -> str:
    if end <= today:
        return "past"
    if start <= today:
        return "current"
    return "future"


def _dasha_view(rows: Any, current: Any, today: date) -> dict[str, Any] | None:
    """Full Vimshottari mahadasha sequence plus antardashas around the present.

    Antardashas are listed for the previous, current and next mahadasha (about
    40 years around today); the complete mahadasha sequence is always kept.
    """
    if not isinstance(rows, list) or not rows:
        return None
    periods = []
    for index, row in enumerate(rows):
        start = date.fromisoformat(row["start_date"])
        if index + 1 < len(rows):
            end = date.fromisoformat(rows[index + 1]["start_date"])
        else:
            end = start + timedelta(days=float(row["duration_years"]) * _YEAR_DAYS)
        periods.append((row["maha_lord"], row["bhukti_lord"], start, end))

    # Group consecutive rows into mahadashas, remembering which one each row belongs to
    # (by position: a lord can recur within the 120-year cycle).
    mahadashas: list[dict[str, Any]] = []
    period_maha_index = []
    for maha, _antar, start, end in periods:
        if mahadashas and mahadashas[-1]["lord"] == maha:
            mahadashas[-1]["end"] = end
        else:
            mahadashas.append({"lord": maha, "start": start, "end": end})
        period_maha_index.append(len(mahadashas) - 1)
    current_index = next(
        (i for i, md in enumerate(mahadashas) if md["start"] <= today < md["end"]), None
    )
    window: set[int] = set()
    if current_index is not None:
        window = {current_index - 1, current_index, current_index + 1}

    view: dict[str, Any] = {
        "system": "Vimshottari",
        "mahadashas": [
            {"lord": md["lord"], "start": md["start"].isoformat(), "end": md["end"].isoformat(),
             "status": _status(md["start"], md["end"], today)}
            for md in mahadashas
        ],
        "antardashas": [
            {"mahadasha": maha, "antardasha": antar, "start": start.isoformat(), "end": end.isoformat(),
             "status": _status(start, end, today)}
            for (maha, antar, start, end), maha_index in zip(periods, period_maha_index)
            if maha_index in window
        ],
        "note": "Antardashas cover the previous, current and next mahadasha; the first mahadasha starts before birth (dasha balance).",
    }
    if isinstance(current, Mapping) and current.get("maha_lord"):
        view["current"] = {key: value for key, value in current.items() if key != "as_of"}
    return view


def _transit_view(
    transits: Any, lagna: int, planets: list[dict[str, Any]], ashtakavarga: Any
) -> dict[str, Any] | None:
    if not isinstance(transits, Mapping) or not transits.get("planets"):
        return None
    moon_sign = SIGN_INDEX[next(row["sign"] for row in planets if row["planet"] == "Moon")]
    sav = _sav_by_sign(ashtakavarga)
    bav = _bav_sign_table(ashtakavarga)
    rows, house_of = [], {}
    for entry in transits["planets"]:
        name = entry.get("planet")
        if name not in PLANETS:
            continue
        sign = _sign_index(entry)
        house_of[name] = _house_from(sign, lagna)
        row: dict[str, Any] = {
            "planet": name,
            "sign": SIGNS[sign],
            "degree": round(float(entry.get("longitude_in_sign", 0.0)), 2),
            "retrograde": bool(entry.get("retrograde", False)),
            "house_from_lagna": house_of[name],
            "house_from_moon": _house_from(sign, moon_sign),
        }
        if sav is not None:
            row["sarvashtakavarga_bindus"] = sav[sign]
        if name in bav:
            row["own_bhinna_bindus"] = bav[name][sign]
        rows.append(row)

    view: dict[str, Any] = {"as_of": transits.get("as_of"), "planets": rows}
    if "Saturn" in house_of:
        saturn_from_moon = next(r["house_from_moon"] for r in rows if r["planet"] == "Saturn")
        phase = {12: "first phase (12th from Moon)", 1: "peak phase (over the Moon)",
                 2: "final phase (2nd from Moon)"}.get(saturn_from_moon)
        view["sade_sati"] = {"active": phase is not None, "phase": phase}
        if saturn_from_moon == 8:
            view["ashtama_shani"] = True
        if saturn_from_moon == 4:
            view["ardhashtama_shani"] = True
    if "Jupiter" in house_of and "Saturn" in house_of:
        jupiter = {house_of["Jupiter"], *_aspected_houses("Jupiter", house_of["Jupiter"])}
        saturn = {house_of["Saturn"], *_aspected_houses("Saturn", house_of["Saturn"])}
        view["double_transit_houses"] = sorted(jupiter & saturn)
    return view


# --- KP ------------------------------------------------------------------


def _kp_view(kp: Any) -> dict[str, Any] | None:
    """Placidus cusps, KP house occupancy and the four-level significator table."""
    if not isinstance(kp, Mapping) or not kp.get("cusps") or not kp.get("planets"):
        return None
    cusps = sorted(kp["cusps"], key=lambda cusp: cusp["house"])
    if len(cusps) != 12:
        return None
    cusp_longitudes = [_absolute_longitude(cusp) for cusp in cusps]
    owner = {cusp["house"]: cusp["sign_lord"] for cusp in cusps}
    planets = {p["planet"]: p for p in kp["planets"] if p.get("planet") in PLANETS}

    def kp_house(longitude: float) -> int:
        for index in range(12):
            start, end = cusp_longitudes[index], cusp_longitudes[(index + 1) % 12]
            span = (end - start) % 360.0
            if (longitude - start) % 360.0 < span:
                return index + 1
        return 12

    house_of = {name: kp_house(_absolute_longitude(entry)) for name, entry in planets.items()}
    star_of = {name: entry["star_lord"] for name, entry in planets.items()}

    def own_houses(name: str) -> list[int]:
        """Houses a planet occupies or owns; nodes also carry their dispositor's."""
        houses = {house_of[name]} if name in house_of else set()
        houses |= {house for house, lord in owner.items() if lord == name}
        if name in NODES and name in planets:
            dispositor = SIGN_LORDS[_sign_index(planets[name])]
            houses |= set(own_houses(dispositor))
        return sorted(houses)

    def signifies(name: str) -> dict[str, list[int]]:
        return {"via_star_lord": own_houses(star_of[name]) if name in star_of else [],
                "own": own_houses(name)}

    house_significators = []
    for house in range(1, 13):
        occupants = [name for name in PLANETS if house_of.get(name) == house]
        house_significators.append({
            "house": house,
            "a_in_star_of_occupants": [n for n in PLANETS if star_of.get(n) in occupants],
            "b_occupants": occupants,
            "c_in_star_of_owner": [n for n in PLANETS if star_of.get(n) == owner[house]],
            "d_owner": owner[house],
        })

    return {
        "ayanamsa": kp.get("ayanamsa"),
        "house_system": kp.get("house_system", "Placidus"),
        "cusps": [
            {
                "house": cusp["house"],
                "sign": cusp["sign"],
                "degree": round(float(cusp["longitude_in_sign"]), 2),
                "sign_lord": cusp["sign_lord"],
                "star_lord": cusp["star_lord"],
                "sub_lord": cusp["sub_lord"],
                "sub_lord_signifies": signifies(cusp["sub_lord"]) if cusp["sub_lord"] in planets else None,
            }
            for cusp in cusps
        ],
        "planets": [
            {
                "planet": name,
                "sign": entry["sign"],
                "degree": round(float(entry["longitude_in_sign"]), 2),
                "kp_house": house_of[name],
                "star_lord": entry["star_lord"],
                "sub_lord": entry["sub_lord"],
                "signifies": signifies(name),
            }
            for name, entry in planets.items()
        ],
        "house_significators": house_significators,
        "ruling_planets": kp.get("ruling_planets"),
    }


# --- metadata ------------------------------------------------------------


def _meta(chart: Mapping[str, Any], domain: str | None, methodology: str, today: date) -> dict[str, Any]:
    raw_meta = chart.get("meta") or {}
    meta: dict[str, Any] = {
        "as_of": today.isoformat(),
        "domain": domain,
        "methodology": methodology,
        "ayanamsa": raw_meta.get("ayanamsa", "unknown"),
        "conventions": [
            "planets/houses/divisional_charts use whole-sign houses counted from that chart's ascendant",
            "kp section uses Placidus cusps; kp_house can differ from the whole-sign house",
            "aspects are Parashari graha drishti; Rahu/Ketu 5/7/9 is common practice, not universal",
            "dignity uses natural (naisargika) friendship; combustion uses Surya Siddhanta orbs",
            "D30, D60 and KP sub-lords near a boundary are sensitive to small birth-time errors",
        ],
    }
    if isinstance(chart.get("kp"), Mapping):
        meta["kp_ayanamsa"] = chart["kp"].get("ayanamsa", "unknown")
    return meta
