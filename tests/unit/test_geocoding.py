import unittest
from unittest.mock import MagicMock, patch

from geopy.exc import GeocoderUnavailable

from app.geocoding import GeocodingServiceError, geocode_indian_place


class GeocodingTests(unittest.TestCase):
    @patch("app.geocoding._geolocator")
    def test_returns_coordinates_for_a_matching_indian_place(self, mock_geolocator):
        location = MagicMock()
        location.latitude = 17.360589
        location.longitude = 78.4740613
        location.address = "Hyderabad, Telangana, India"
        mock_geolocator.geocode.return_value = location

        result = geocode_indian_place("Hyderabad, India")

        self.assertEqual(result["latitude"], 17.360589)
        self.assertEqual(result["longitude"], 78.4740613)
        mock_geolocator.geocode.assert_called_once_with(
            "Hyderabad, India", country_codes="in", exactly_one=True, timeout=10
        )

    @patch("app.geocoding._geolocator")
    def test_returns_none_when_place_is_not_found(self, mock_geolocator):
        mock_geolocator.geocode.return_value = None

        self.assertIsNone(geocode_indian_place("Unknown place"))

    @patch("app.geocoding._geolocator")
    def test_raises_distinct_error_when_provider_is_unavailable(self, mock_geolocator):
        mock_geolocator.geocode.side_effect = GeocoderUnavailable("TLS failure")

        with self.assertRaisesRegex(
            GeocodingServiceError, "temporarily unavailable"
        ):
            geocode_indian_place("Hyderabad, India")


if __name__ == "__main__":
    unittest.main()