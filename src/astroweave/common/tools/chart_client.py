from __future__ import annotations

import os

import httpx

from astroweave.common.config import get_logger

logger = get_logger(__name__)

CHART_SERVICE_URL = os.environ.get("ASTROWEAVE_CHART_SERVICE_URL", "http://127.0.0.1:8100")


def get_birth_chart(
    date: str,
    time: str,
    latitude: float,
    longitude: float,
    utc_offset_hours: float,
    place_name: str | None = None,
    varga_factors: list[int] | None = None,
    include_dasha_bhukti: bool = True,
    include_bhava_chart: bool = True,
    include_ashtakavarga: bool = True,
    timeout: float = 10.0,
) -> dict[str, object]:
    """Fetch a birth chart from the isolated chart_service over HTTP.

    chart_service wraps PyJHora (AGPL-3.0) and is kept as a separate process;
    this client only talks to it over the network, it never imports PyJHora.

    Returns a dict with keys: d1 (rasi chart + KP sub-lords), divisional_charts
    (D9/D10/D7/D12/D3/D24 by default, or whatever varga_factors is given),
    dasha_bhukti, bhava_chart and ashtakavarga - toggle the include_* flags to
    skip sections that aren't needed.
    """
    payload = {
        "date": date,
        "time": time,
        "latitude": latitude,
        "longitude": longitude,
        "utc_offset_hours": utc_offset_hours,
        "place_name": place_name,
        "varga_factors": varga_factors,
        "include_dasha_bhukti": include_dasha_bhukti,
        "include_bhava_chart": include_bhava_chart,
        "include_ashtakavarga": include_ashtakavarga,
    }
    logger.info("Requesting chart from chart_service date=%s time=%s", date, time)
    response = httpx.post(f"{CHART_SERVICE_URL.rstrip('/')}/chart", json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()
