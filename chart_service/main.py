from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from jhora import const, utils
from jhora.horoscope.chart import ashtakavarga, charts
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
# Field order returned by charts.get_KP_lords_from_planet_positions() for each planet/ascendant.
KP_LORD_FIELDS = [
    "nakshatra_lord", "sub_lord", "pratyantar_lord", "sookshma_lord", "praana_lord", "deha_lord",
]
# Default divisional (varga) charts requested alongside D1, keyed by their varga factor.
DEFAULT_VARGA_FACTORS = {"D9": 9, "D10": 10, "D7": 7, "D12": 12, "D3": 3, "D24": 24}
# Ashtakavarga only covers the seven classical grahas plus the ascendant (no Rahu/Ketu).
ASHTAKAVARGA_ROW_LABELS = PLANET_NAMES[:7] + ["Ascendant"]


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


@app.get("/health")
def health() -> dict[str, str]:
    logger.debug("Health check requested")
    return {"status": "ok", "service": "astroweave-chart-service"}


def _format_planet_positions(positions: list, kp_lords_by_id: dict | None = None) -> dict[str, object]:
    """Shape charts.rasi_chart()/divisional_chart() output into ascendant + planets."""
    ascendant: dict[str, object] | None = None
    planets: list[dict[str, object]] = []
    for planet_id, (sign_index, longitude_in_sign) in positions:
        entry: dict[str, object] = {
            "sign": RASI_NAMES[sign_index],
            "sign_index": sign_index,
            "longitude_in_sign": round(longitude_in_sign, 4),
        }
        if kp_lords_by_id is not None:
            kp_no, *lord_ids = kp_lords_by_id[planet_id]
            entry["kp"] = {
                "kp_number": kp_no,
                **{field: _planet_label(lord_id) for field, lord_id in zip(KP_LORD_FIELDS, lord_ids)},
            }
        if planet_id == "L":
            ascendant = entry
        else:
            entry["planet"] = PLANET_NAMES[planet_id]
            planets.append(entry)
    return {"ascendant": ascendant, "planets": planets}


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
    house_to_planet_list = utils.get_house_planet_list_from_planet_positions(positions)
    binna, samudhaya, _prastara = ashtakavarga.get_ashtaka_varga(house_to_planet_list)
    return {
        "binna": dict(zip(ASHTAKAVARGA_ROW_LABELS, binna)),
        "samudhaya": samudhaya,
    }


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

    place = drik.Place(
        request.place_name or "unspecified",
        request.latitude,
        request.longitude,
        request.utc_offset_hours,
    )
    julian_day = drik.utils.julian_day_number((year, month, day), (hour, minute, second))

    d1_positions = charts.rasi_chart(julian_day, place)
    kp_lords_by_id = charts.get_KP_lords_from_planet_positions(d1_positions)
    result: dict[str, object] = {"d1": _format_planet_positions(d1_positions, kp_lords_by_id)}

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
    if request.include_bhava_chart:
        result["bhava_chart"] = _bhava_chart_table(julian_day, place)
    if request.include_ashtakavarga:
        result["ashtakavarga"] = _ashtakavarga_table(d1_positions)

    logger.info("Chart computed successfully date=%s time=%s", request.date, request.time)
    return result
