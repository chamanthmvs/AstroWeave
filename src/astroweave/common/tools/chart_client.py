from __future__ import annotations

import os

import httpx

from astroweave.common.config import get_logger

logger = get_logger(__name__)

CHART_SERVICE_URL = os.environ.get("ASTROWEAVE_CHART_SERVICE_URL", "http://127.0.0.1:8100")

# Free hosts (e.g. Render free tier) sleep when idle and can take ~30-50s to wake
# on the first request. Default generously so a cold chart service doesn't look
# like an outage; override with ASTROWEAVE_CHART_TIMEOUT.
def _default_timeout() -> float:
    try:
        return float(os.environ.get("ASTROWEAVE_CHART_TIMEOUT", "60"))
    except ValueError:
        return 60.0


def full_chart_timeout() -> float:
    """The full chart (all sections) is far heavier; allow much longer, since it
    runs in a background job and is cached, not in a user-facing request."""
    try:
        return float(os.environ.get("ASTROWEAVE_FULL_CHART_TIMEOUT", "240"))
    except ValueError:
        return 240.0


class ChartServiceUnavailable(RuntimeError):
    """Raised when the chart_service cannot be reached (down, unreachable, or
    timed out). This is a transport failure, not a bad-request/computation
    error, so callers can surface it as an HTTP 503 rather than a soft
    "could not compute a chart" message."""


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
    include_shadbala: bool = True,
    include_yogas: bool = True,
    include_transits: bool = True,
    include_current_dasha: bool = True,
    include_kp: bool = True,
    timeout: float | None = None,
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
        "include_shadbala": include_shadbala,
        "include_yogas": include_yogas,
        "include_transits": include_transits,
        "include_current_dasha": include_current_dasha,
        "include_kp": include_kp,
    }
    logger.info("Requesting chart from chart_service date=%s time=%s", date, time)
    return _post("/chart", payload, timeout if timeout is not None else _default_timeout())


def match_charts(
    person: dict,
    partner: dict,
    person_is_groom: bool = True,
    timeout: float | None = None,
) -> dict[str, object]:
    """Kundli Milan for two births via chart_service /match.

    `person` and `partner` are birth-detail dicts (date, time, latitude,
    longitude, utc_offset_hours, place_name, optional time_known). Returns the
    North Ashtakoota + South porutham + Manglik result.
    """
    payload = {"person": person, "partner": partner, "person_is_groom": person_is_groom}
    logger.info("Requesting match from chart_service")
    return _post("/match", payload, timeout if timeout is not None else _default_timeout())


def _post(path: str, payload: dict, timeout: float) -> dict[str, object]:
    try:
        response = httpx.post(f"{CHART_SERVICE_URL.rstrip('/')}{path}", json=payload, timeout=timeout)
    except httpx.TransportError as error:
        # Connection refused, DNS failure, timeout, etc. — the service is down
        # or unreachable. Distinct from a bad response, which we let through.
        logger.error("chart_service unreachable at %s: %s", CHART_SERVICE_URL, error)
        raise ChartServiceUnavailable(
            "The astrology engine is waking up (it sleeps when idle on free hosting). "
            "Please try again in a few seconds."
        ) from error
    response.raise_for_status()
    return response.json()
