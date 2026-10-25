import unittest
from unittest.mock import MagicMock, patch

import httpx

from astroweave.common.tools import chart_client
from astroweave.common.tools.chart_client import (
    ChartServiceUnavailable,
    get_birth_chart,
)

_BIRTH = {
    "date": "1990-01-01",
    "time": "12:00:00",
    "latitude": 13.08,
    "longitude": 80.27,
    "utc_offset_hours": 5.5,
}


class ChartClientTests(unittest.TestCase):
    @patch("astroweave.common.tools.chart_client.httpx.post")
    def test_transport_error_raises_chart_service_unavailable(self, mock_post):
        mock_post.side_effect = httpx.ConnectError("connection refused")

        with self.assertRaises(ChartServiceUnavailable) as caught:
            get_birth_chart(**_BIRTH)

        # The message is user-friendly (no leaked dev command).
        message = str(caught.exception)
        self.assertIn("waking up", message)
        self.assertNotIn("cd chart_service", message)

    @patch("astroweave.common.tools.chart_client.httpx.post")
    def test_bad_request_4xx_propagates_as_http_error(self, mock_post):
        # A 4xx (genuine bad request) stays an httpx error, not a 503-style outage.
        response = MagicMock()
        response.status_code = 400
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "bad request", request=MagicMock(), response=MagicMock()
        )
        mock_post.return_value = response

        with self.assertRaises(httpx.HTTPStatusError):
            get_birth_chart(**_BIRTH)

    @patch("astroweave.common.tools.chart_client.httpx.post")
    def test_5xx_is_treated_as_unavailable(self, mock_post):
        # A 5xx (busy/restarting/crashed service) becomes ChartServiceUnavailable.
        response = MagicMock()
        response.status_code = 502
        mock_post.return_value = response

        with self.assertRaises(ChartServiceUnavailable):
            get_birth_chart(**_BIRTH)

    @patch("astroweave.common.tools.chart_client.httpx.post")
    def test_successful_call_returns_chart_payload(self, mock_post):
        response = MagicMock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = {"d1": {"ok": True}}
        mock_post.return_value = response

        self.assertEqual(get_birth_chart(**_BIRTH), {"d1": {"ok": True}})


if __name__ == "__main__":
    unittest.main()
