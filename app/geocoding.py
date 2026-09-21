"""Place name -> (latitude, longitude) resolution, restricted to India.

AstroWeave is currently scoped to Indian users only, so every account uses a
fixed +5.5 (IST) UTC offset - there's no need to ask for it, and no need to
support geocoding outside India. Uses geopy's Nominatim (OpenStreetMap) since
it's free, keyless, and reliable enough for city/town-level lookups.
"""

from __future__ import annotations

import logging
import ssl

import certifi
from geopy.exc import GeopyError
from geopy.geocoders import Nominatim

logger = logging.getLogger(__name__)

INDIA_UTC_OFFSET_HOURS = 5.5


class GeocodingServiceError(RuntimeError):
    """Raised when the geocoding provider cannot be reached securely."""


_ssl_context = ssl.create_default_context(cafile=certifi.where())
_geolocator = Nominatim(user_agent="astroweave-app", ssl_context=_ssl_context)


def geocode_indian_place(place_name: str) -> dict[str, object] | None:
    """Resolve a place name to coordinates, restricted to India.

    Returns {"latitude": float, "longitude": float, "display_name": str} on
    success, or None if the place couldn't be found (or isn't in India) so
    the caller can ask the user to enter a nearby city name instead.
    """
    if not place_name or not place_name.strip():
        return None
    try:
        location = _geolocator.geocode(
            place_name.strip(), country_codes="in", exactly_one=True, timeout=10
        )
    except GeopyError as error:
        logger.exception("Geocoding failed for place_name=%s", place_name)
        raise GeocodingServiceError(
            "The place lookup service is temporarily unavailable. Please try again."
        ) from error
    if location is None:
        return None
    return {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "display_name": location.address,
    }
