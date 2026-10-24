from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from jhora import const, utils
from jhora.horoscope.chart import ashtakavarga, charts, strength, yoga
from jhora.horoscope.dhasa.graha import vimsottari
from jhora.panchanga import drik


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger(__name__)

# AGPL-3.0 licensed (PyJHora). Kept as its own network-isolated process so the
# AstroWeave backend can stay a separate program that merely calls this HTTP API.
app = FastAPI(
    title="AstroWeave Chart Service",
    description="Isolated PyJHora-backed birth chart calculation service.",
    version="0.1.0",
)

PLANET_NAMES = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
RASI_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
# Default divisional (varga) charts requested alongside D1, keyed by their varga factor:
# D2 wealth, D3 courage/siblings, D4 property/fixed assets, D7 children, D9 spouse and
# overall strength, D10 career, D12 parents, D24 education, D30 misfortune/injury, and
# D60 (needs a birth time accurate to about a minute to be meaningful).
DEFAULT_VARGA_FACTORS = {
    "D2": 2, "D3": 3, "D4": 4, "D7": 7, "D9": 9, "D10": 10, "D12": 12, "D24": 24, "D30": 30, "D60": 60,
}
# Lahiri (Chitrapaksha) is the standard for Parashari work; KP uses its own
# Krishnamurti ayanamsa. PyJHora's library default (True Pushya) is neither, so both
# are always set explicitly - the difference moves sub-lords and dasha dates.
DEFAULT_AYANAMSA = "LAHIRI"
DEFAULT_KP_AYANAMSA = "KP"
# Sign lords, Aries..Pisces (Parashari rulership; nodes rule no sign).
SIGN_LORDS = [
    "Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
    "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter",
]
# Weekday lords for KP ruling planets, indexed by datetime.weekday() (Monday=0).
WEEKDAY_LORDS = ["Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Sun"]
NODE_IDS = (7, 8)
# swisseph holds the ayanamsa (sidereal mode) as process-global state and PyJHora
# mirrors it in a module constant, so a chart must be computed start-to-finish
# without another request switching the ayanamsa underneath it.
_CALCULATION_LOCK = threading.Lock()
# Ashtakavarga only covers the seven classical grahas plus the ascendant (no Rahu/Ketu).
ASHTAKAVARGA_ROW_LABELS = PLANET_NAMES[:7] + ["Ascendant"]
# Shadbala/dasha-depth calculations only cover the seven classical grahas (no Rahu/Ketu).
CLASSICAL_PLANET_NAMES = PLANET_NAMES[:7]


def _planet_label(planet_id: int | str) -> str:
    return "Ascendant" if planet_id == "L" else PLANET_NAMES[planet_id]


class ChartRequest(BaseModel):
    date: str = Field(..., description="Birth date as YYYY-MM-DD")
    time: str = Field(..., description="Birth time as HH:MM:SS (24-hour, local)")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    utc_offset_hours: float = Field(..., description="e.g. 5.5 for IST")
    place_name: str | None = Field(default=None)
    varga_factors: list[int] | None = Field(
        default=None,
        description="Divisional chart factors to compute besides D1, e.g. [9, 10, 7]. Defaults to a common set.",
    )
    include_dasha_bhukti: bool = Field(default=True)
    include_bhava_chart: bool = Field(default=True)
    include_ashtakavarga: bool = Field(default=True)
    include_shadbala: bool = Field(default=True)
    include_yogas: bool = Field(default=True)
    include_transits: bool = Field(default=True)
    include_current_dasha: bool = Field(default=True)
    include_kp: bool = Field(default=True)
    pratyantardasha_years_back: float = Field(
        default=1, ge=0, le=20, description="Pratyantardashas listed from this many years before today."
    )
    pratyantardasha_years_ahead: float = Field(
        default=5, ge=0, le=30, description="Pratyantardashas listed up to this many years after today."
    )
    ayanamsa: str = Field(
        default=DEFAULT_AYANAMSA,
        description="Ayanamsa for the Parashari sections (D1, vargas, dasha, transits, ...).",
    )
    kp_ayanamsa: str = Field(
        default=DEFAULT_KP_AYANAMSA,
        description="Ayanamsa for the KP section (planet/cusp star and sub lords, ruling planets).",
    )


@app.get("/health")
def health() -> dict[str, str]:
    logger.debug("Health check requested")
    return {"status": "ok", "service": "astroweave-chart-service"}


def _format_planet_positions(positions: list, retrograde_ids: list[int] | None = None) -> dict[str, object]:
    """Shape charts.rasi_chart()/divisional_chart() output into ascendant + planets.

    `retrograde_ids` comes from drik.planets_in_retrograde() (true planetary
    speed). Rahu/Ketu are PyJHora's mean nodes, which always move retrograde,
    so they are flagged as such; vargas omit the flag (it is a D1 property).
    """
    ascendant: dict[str, object] | None = None
    planets: list[dict[str, object]] = []
    for planet_id, (sign_index, longitude_in_sign) in positions:
        entry: dict[str, object] = {
            "sign": RASI_NAMES[sign_index],
            "sign_index": sign_index,
            "longitude_in_sign": round(longitude_in_sign, 4),
        }
        if planet_id == "L":
            ascendant = entry
        else:
            entry["planet"] = PLANET_NAMES[planet_id]
            if retrograde_ids is not None:
                entry["retrograde"] = planet_id in NODE_IDS or planet_id in retrograde_ids
            planets.append(entry)
    return {"ascendant": ascendant, "planets": planets}


def _kp_lords(lord_ids: list) -> dict[str, object]:
    """KP lords of one longitude: [kp_no, star, sub, sub-sub, ...] -> named fields."""
    _kp_number, star_lord, sub_lord, sub_sub_lord, *_deeper = lord_ids
    return {
        "star_lord": _planet_label(star_lord),
        "sub_lord": _planet_label(sub_lord),
        "sub_sub_lord": _planet_label(sub_sub_lord),
    }


def _kp_section(julian_day: float, place: drik.Place, jd_now: float, now_local: datetime) -> dict[str, object]:
    """KP (Krishnamurti Paddhati) data; call with the KP ayanamsa active.

    KP judges houses by their *cusps* (Placidus), not by whole signs, and by the
    star/sub lords of each cusp and planet - so these come from their own
    ayanamsa and house system rather than being bolted onto the D1 entries.
    """
    natal = charts.rasi_chart(julian_day, place)
    natal_lords = charts.get_KP_lords_from_planet_positions(natal)
    planets = []
    for planet_id, (sign_index, longitude_in_sign) in natal:
        if planet_id == "L":
            continue
        planets.append({
            "planet": PLANET_NAMES[planet_id],
            "sign": RASI_NAMES[sign_index],
            "longitude_in_sign": round(longitude_in_sign, 4),
            **_kp_lords(natal_lords[planet_id]),
        })

    cusp_longitudes = drik.bhaava_madhya_kp(julian_day, place)
    cusp_positions = [
        [f"C{house}", (int(longitude // 30) % 12, longitude % 30)]
        for house, longitude in enumerate((lon % 360 for lon in cusp_longitudes), start=1)
    ]
    cusp_lords = charts.get_KP_lords_from_planet_positions(cusp_positions)
    cusps = [
        {
            "house": house,
            "sign": RASI_NAMES[sign_index],
            "longitude_in_sign": round(longitude_in_sign, 4),
            "sign_lord": SIGN_LORDS[sign_index],
            **_kp_lords(cusp_lords[f"C{house}"]),
        }
        for house, (_key, (sign_index, longitude_in_sign)) in enumerate(cusp_positions, start=1)
    ]

    # Ruling planets: the moment of judgment (now), cast for the birth place.
    now_positions = charts.rasi_chart(jd_now, place)
    now_lords = charts.get_KP_lords_from_planet_positions(now_positions)
    by_id = dict(now_positions)
    def _ruler(point_id) -> dict[str, object]:
        sign_index, _longitude = by_id[point_id]
        lords = _kp_lords(now_lords[point_id])
        return {
            "sign": RASI_NAMES[sign_index],
            "sign_lord": SIGN_LORDS[sign_index],
            "star_lord": lords["star_lord"],
            "sub_lord": lords["sub_lord"],
        }
    ruling_planets = {
        "as_of": now_local.strftime("%Y-%m-%d %H:%M:%S"),
        "ascendant": _ruler("L"),
        "moon": _ruler(1),
        "day_lord": WEEKDAY_LORDS[now_local.weekday()],
    }
    return {
        "house_system": "Placidus (KP cusps)",
        "planets": planets,
        "cusps": cusps,
        "ruling_planets": ruling_planets,
    }


def _dasha_bhukti_table(julian_day: float, place: drik.Place) -> list[dict[str, object]]:
    _, rows = vimsottari.get_vimsottari_dhasa_bhukthi(
        julian_day, place, dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,
    )
    table = []
    for (maha_lord, bhukti_lord), (year, month, day, fractional_hour), duration_years in rows:
        table.append({
            "maha_lord": _planet_label(maha_lord),
            "bhukti_lord": _planet_label(bhukti_lord),
            "start_date": f"{year:04d}-{month:02d}-{day:02d}",
            "start_hour": round(fractional_hour, 2),
            "duration_years": round(duration_years, 4),
        })
    return table


def _pratyantardasha_window(
    julian_day: float, place: drik.Place, now_local: datetime, years_back: float, years_ahead: float
) -> dict[str, object]:
    """Vimshottari pratyantardashas (third level) overlapping a window around today.

    The full table has 729 rows over 120 years; only the window that timing
    questions need is returned. Each period ends where the next one starts.
    """
    _, rows = vimsottari.get_vimsottari_dhasa_bhukthi(
        julian_day, place, dhasa_level_index=const.MAHA_DHASA_DEPTH.PRATYANTARA,
    )
    starts = [datetime(year, month, day).date() for _lords, (year, month, day, _hour), _duration in rows]
    today = now_local.date()
    window_start = today - timedelta(days=years_back * 365.2425)
    window_end = today + timedelta(days=years_ahead * 365.2425)
    periods = []
    for index, ((maha, antar, pratyantar), _start, duration_years) in enumerate(rows):
        start = starts[index]
        end = starts[index + 1] if index + 1 < len(rows) else start + timedelta(days=duration_years * 365.2425)
        if end <= window_start or start >= window_end:
            continue
        periods.append({
            "maha_lord": _planet_label(maha),
            "antardasha_lord": _planet_label(antar),
            "pratyantardasha_lord": _planet_label(pratyantar),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        })
    return {
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "periods": periods,
    }


def _bhava_chart_table(julian_day: float, place: drik.Place) -> list[dict[str, object]]:
    table = []
    for sign_index, (house_start, house_cusp, house_end), planets_in_house in charts.bhava_chart(julian_day, place):
        table.append({
            "sign": RASI_NAMES[sign_index],
            "sign_index": sign_index,
            "house_start_longitude": round(house_start, 4),
            "house_cusp_longitude": round(house_cusp, 4),
            "house_end_longitude": round(house_end, 4),
            "planets": [_planet_label(planet_id) for planet_id in planets_in_house],
        })
    return table


def _ashtakavarga_table(positions: list) -> dict[str, object]:
    """Bhinna (per-planet) and Sarva (total) ashtakavarga bindus, keyed by sign.

    PyJHora returns 12-element arrays indexed by sign (Aries=0), not by house
    from the ascendant; keying them by sign name removes that ambiguity.
    """
    sign_to_planet_list = utils.get_house_planet_list_from_planet_positions(positions)
    binna, samudhaya, _prastara = ashtakavarga.get_ashtaka_varga(sign_to_planet_list)
    return {
        "indexed_by": "sign",
        "binna": {
            label: dict(zip(RASI_NAMES, row)) for label, row in zip(ASHTAKAVARGA_ROW_LABELS, binna)
        },
        "samudhaya": dict(zip(RASI_NAMES, samudhaya)),
    }


def _shadbala_table(julian_day: float, place: drik.Place) -> dict[str, dict[str, float]]:
    """Planetary strength (Shadbala), in rupas and as a ratio to the classical minimum.

    A `strength_ratio` >= 1.0 means the planet meets or exceeds the strength
    classical texts consider required to give good results.
    """
    *_components, sb_rupa, sb_strength = strength.shad_bala(julian_day, place)
    return {
        name: {"strength_rupas": sb_rupa[index], "strength_ratio": sb_strength[index]}
        for index, name in enumerate(CLASSICAL_PLANET_NAMES)
    }


def _yoga_list(julian_day: float, place: drik.Place) -> list[dict[str, str]]:
    """Classical yogas (planetary combinations) present in the D1 chart."""
    yoga_results, _found, _total = yoga.get_yoga_details(julian_day, place, divisional_chart_factor=1)
    return [
        {"name": details[1], "description": details[2], "benefits": details[3]}
        for details in yoga_results.values()
    ]


def _now_julian_day(place: drik.Place) -> tuple[float, datetime]:
    now_local = datetime.now(timezone.utc) + timedelta(hours=place.timezone)
    julian_day = drik.utils.julian_day_number(
        (now_local.year, now_local.month, now_local.day),
        (now_local.hour, now_local.minute, now_local.second),
    )
    return julian_day, now_local


def _transit_positions(place: drik.Place, jd_now: float, now_local: datetime) -> dict[str, object]:
    """Where the planets are right now, in the birth place's sky - for gochara analysis."""
    formatted = _format_planet_positions(
        charts.rasi_chart(jd_now, place), retrograde_ids=drik.planets_in_retrograde(jd_now, place)
    )
    formatted["as_of"] = now_local.strftime("%Y-%m-%d %H:%M:%S")
    return formatted


def _date_label(date_tuple: tuple) -> str:
    year, month, day, *_hour = date_tuple
    return f"{year:04d}-{month:02d}-{day:02d}"


def _current_dasha(julian_day: float, place: drik.Place, jd_now: float, now_local: datetime) -> dict[str, object]:
    """The Mahadasha/Antardasha/Pratyantardasha active right now, with each level's span."""
    running = vimsottari.get_running_dhasa_for_given_date(
        jd_now, julian_day, place, dhasa_level_index=const.MAHA_DHASA_DEPTH.PRATYANTARA
    )
    level_keys = ["maha", "antardasha", "pratyantardasha"]
    result: dict[str, object] = {"as_of": now_local.strftime("%Y-%m-%d %H:%M:%S")}
    for level_key, (lords, start, end) in zip(level_keys, running):
        result[f"{level_key}_lord"] = _planet_label(lords[-1])
        result[f"{level_key}_start"] = _date_label(start)
        result[f"{level_key}_end"] = _date_label(end)
    return result


@app.post("/chart")
def compute_chart(request: ChartRequest) -> dict[str, object]:
    logger.info(
        "Computing chart date=%s time=%s lat=%s lon=%s",
        request.date, request.time, request.latitude, request.longitude,
    )
    try:
        year, month, day = (int(part) for part in request.date.split("-"))
        hour, minute, second = (int(part) for part in request.time.split(":"))
    except ValueError as error:
        logger.warning("Rejected chart request with invalid date/time: %s", error)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid date/time format: {error}",
        ) from error

    available_modes = {mode.upper() for mode in const.available_ayanamsa_modes}
    for field_name in ("ayanamsa", "kp_ayanamsa"):
        if getattr(request, field_name).upper() not in available_modes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported {field_name} '{getattr(request, field_name)}'. "
                f"Choose one of: {', '.join(sorted(available_modes))}",
            )

    place = drik.Place(
        request.place_name or "unspecified",
        request.latitude,
        request.longitude,
        request.utc_offset_hours,
    )
    julian_day = drik.utils.julian_day_number((year, month, day), (hour, minute, second))
    jd_now, now_local = _now_julian_day(place)

    with _CALCULATION_LOCK:
        drik.set_ayanamsa_mode(request.ayanamsa.upper())
        result: dict[str, object] = {
            "meta": {
                "ayanamsa": request.ayanamsa.upper(),
                "ayanamsa_degrees": round(drik.get_ayanamsa_value(julian_day), 4),
                "zodiac": "sidereal",
                "nodes": "mean nodes (always retrograde)",
                "bhava_chart_house_system": "equal houses, ascendant degree at the middle of house 1",
            }
        }
        d1_positions = charts.rasi_chart(julian_day, place)
        result["d1"] = _format_planet_positions(
            d1_positions, retrograde_ids=drik.planets_in_retrograde(julian_day, place)
        )

        varga_factors = (
            {f"D{factor}": factor for factor in request.varga_factors}
            if request.varga_factors is not None
            else DEFAULT_VARGA_FACTORS
        )
        divisional_charts: dict[str, object] = {}
        for label, factor in varga_factors.items():
            varga_positions = charts.divisional_chart(julian_day, place, divisional_chart_factor=factor)
            divisional_charts[label] = _format_planet_positions(varga_positions)
        result["divisional_charts"] = divisional_charts

        if request.include_dasha_bhukti:
            result["dasha_bhukti"] = _dasha_bhukti_table(julian_day, place)
            result["pratyantardashas"] = _pratyantardasha_window(
                julian_day, place, now_local,
                request.pratyantardasha_years_back, request.pratyantardasha_years_ahead,
            )
        if request.include_bhava_chart:
            result["bhava_chart"] = _bhava_chart_table(julian_day, place)
        if request.include_ashtakavarga:
            result["ashtakavarga"] = _ashtakavarga_table(d1_positions)
        if request.include_shadbala:
            result["shadbala"] = _shadbala_table(julian_day, place)
        if request.include_yogas:
            result["yogas"] = _yoga_list(julian_day, place)
        if request.include_transits:
            result["transits"] = _transit_positions(place, jd_now, now_local)
        if request.include_current_dasha:
            result["current_dasha"] = _current_dasha(julian_day, place, jd_now, now_local)

        if request.include_kp:
            drik.set_ayanamsa_mode(request.kp_ayanamsa.upper())
            kp = _kp_section(julian_day, place, jd_now, now_local)
            kp["ayanamsa"] = request.kp_ayanamsa.upper()
            kp["ayanamsa_degrees"] = round(drik.get_ayanamsa_value(julian_day), 4)
            result["kp"] = kp

    logger.info("Chart computed successfully date=%s time=%s", request.date, request.time)
    return result


# --- Kundli matching (Ashtakoota / Guna Milan + South poruthams) -----------
# Compatibility math is PyJHora's validated Ashtakoota engine (classical nadi,
# gana, bhakoot, mahendra, vedha, rajju rules verified by hand in
# chart_service/test_match.py). Nothing here invents a score.

from jhora.horoscope.match import compatibility as _compat  # noqa: E402
from jhora.horoscope.match.compatibility import Ashtakoota  # noqa: E402

# PyJHora ships a typo in the South rajju "aarohana" set for the neck group:
# neck_aaroga_rajju = [413, 22] should be [4, 13, 22] (4 and 13 got concatenated).
# Left uncorrected it misclassifies Rohini(4)/Hasta(13) and gives a wrong South
# rajju verdict against neck-avarohana stars. Correct it here. (Verified against
# the classical aarohana/avarohana grouping in test_match.py.)
if 413 in _compat.neck_aaroga_rajju:
    _compat.neck_aaroga_rajju = [4, 13, 22]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu",
    "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta",
    "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha",
    "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada",
    "Uttara Bhadrapada", "Revati",
]
NAKSHATRA_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
MANGLIK_HOUSES = {1, 2, 4, 7, 8, 12}  # Mars in these houses = Kuja/Mangal dosha
# North Ashtakoota: (label, max points), in the order compatibility_score() returns them.
_NORTH_KOOTAS = [
    ("Varna", 1), ("Vasya", 2), ("Gana", 6), ("Tara", 3),
    ("Yoni", 4), ("Graha Maitri", 5), ("Bhakoot", 7), ("Nadi", 8),
]
# South 10 poruthams -> their index in compatibility_score(method="South").
_SOUTH_PORUTHAMS = [
    ("Dina", 3), ("Gana", 2), ("Mahendra", 9), ("Stree Dheerga", 12), ("Yoni", 4),
    ("Rasi", 6), ("Rasyadhipathi", 5), ("Vasya", 1), ("Rajju", 11), ("Vedha", 10),
]


class MatchBirth(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD")
    time: str = Field(..., description="HH:MM:SS (24-hour, local)")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    utc_offset_hours: float
    place_name: str | None = None
    time_known: bool = True


class MatchRequest(BaseModel):
    person: MatchBirth
    partner: MatchBirth
    person_is_groom: bool = Field(default=True, description="If true, person=groom/boy, partner=bride/girl.")
    ayanamsa: str = Field(default=DEFAULT_AYANAMSA)


def _match_birth_jd_place(birth: MatchBirth):
    year, month, day = (int(p) for p in birth.date.split("-"))
    hour, minute, second = (int(p) for p in birth.time.split(":"))
    place = drik.Place(birth.place_name or "unspecified", birth.latitude, birth.longitude, birth.utc_offset_hours)
    return drik.utils.julian_day_number((year, month, day), (hour, minute, second)), place


def _match_points(birth: MatchBirth) -> dict[str, object]:
    """Moon nakshatra+pada, Moon rasi, lagna, and Manglik status for one birth.
    Call with the Parashari ayanamsa already set (inside the calculation lock)."""
    julian_day, place = _match_birth_jd_place(birth)
    positions = dict(charts.rasi_chart(julian_day, place))
    moon_sign, moon_long = positions[1]
    mars_sign, _mars_long = positions[2]
    lagna_sign, _lagna_long = positions["L"]
    nak_number, pada, _rem = drik.nakshatra_pada(moon_sign * 30 + moon_long)
    house = lambda sign: (sign - lagna_sign) % 12 + 1
    mars_house_lagna = (mars_sign - lagna_sign) % 12 + 1
    mars_house_moon = (mars_sign - moon_sign) % 12 + 1
    return {
        "rasi": RASI_NAMES[moon_sign],
        "rasi_index": moon_sign,
        "nakshatra": NAKSHATRAS[nak_number - 1],
        "nakshatra_number": nak_number,
        "pada": pada,
        "nakshatra_lord": NAKSHATRA_LORDS[(nak_number - 1) % 9],
        "lagna": RASI_NAMES[lagna_sign],
        "lagna_index": lagna_sign,
        "time_known": birth.time_known,
        "manglik": {
            "mars_house_from_lagna": mars_house_lagna,
            "mars_house_from_moon": mars_house_moon,
            "is_manglik": mars_house_lagna in MANGLIK_HOUSES,
            "manglik_from_moon": mars_house_moon in MANGLIK_HOUSES,
        },
    }


def _ashtakoota(groom: dict, bride: dict) -> dict[str, object]:
    args = (groom["nakshatra_number"], groom["pada"], bride["nakshatra_number"], bride["pada"])
    north = Ashtakoota(*args, method="North").compatibility_score()
    south = Ashtakoota(*args, method="South").compatibility_score()

    kootas = []
    for index, (label, maximum) in enumerate(_NORTH_KOOTAS):
        score = round(float(north[index]), 1)
        kootas.append({"koota": label, "score": score, "max": maximum, "favourable": score > 0})
    total = round(float(north[8]), 1)

    poruthams = [{"porutham": label, "matched": bool(south[idx])} for label, idx in _SOUTH_PORUTHAMS]
    matched = sum(p["matched"] for p in poruthams)

    return {
        "north": {
            "system": "Ashtakoota / Guna Milan (North Indian, 36 points)",
            "kootas": kootas,
            "total": total,
            "out_of": 36,
            "nadi_dosha": kootas[7]["score"] == 0,     # Nadi == 0
            "bhakoot_dosha": kootas[6]["score"] == 0,  # Bhakoot == 0
        },
        "south": {
            "system": "Dasa Porutham (South Indian, 10 poruthams)",
            "poruthams": poruthams,
            "matched_count": matched,
            "out_of": 10,
            "minimum_poruthams_met": bool(south[13]),
        },
    }


@app.post("/match")
def compute_match(request: MatchRequest) -> dict[str, object]:
    """Kundli Milan for two births: North Ashtakoota + South poruthams + Manglik."""
    for who, birth in (("person", request.person), ("partner", request.partner)):
        try:
            [int(p) for p in birth.date.split("-")]
            [int(p) for p in birth.time.split(":")]
        except ValueError as error:
            raise HTTPException(status_code=422, detail=f"Invalid {who} date/time: {error}") from error
    if request.ayanamsa.upper() not in {m.upper() for m in const.available_ayanamsa_modes}:
        raise HTTPException(status_code=422, detail=f"Unsupported ayanamsa '{request.ayanamsa}'.")

    with _CALCULATION_LOCK:
        drik.set_ayanamsa_mode(request.ayanamsa.upper())
        person = _match_points(request.person)
        partner = _match_points(request.partner)

    groom, bride = (person, partner) if request.person_is_groom else (partner, person)
    result = _ashtakoota(groom, bride)
    result["person"] = person
    result["partner"] = partner
    result["roles"] = {
        "groom": "person" if request.person_is_groom else "partner",
        "bride": "partner" if request.person_is_groom else "person",
    }
    result["manglik"] = {
        "person": person["manglik"],
        "partner": partner["manglik"],
        "both_manglik": person["manglik"]["is_manglik"] and partner["manglik"]["is_manglik"],
    }
    result["meta"] = {"ayanamsa": request.ayanamsa.upper(), "zodiac": "sidereal"}
    logger.info("Match computed north=%s/36 south=%s/10", result["north"]["total"], result["south"]["matched_count"])
    return result
