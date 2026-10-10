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

        # The message should point the operator at the unreachable service.
        self.assertIn(chart_client.CHART_SERVICE_URL, str(caught.exception))

    @patch("astroweave.common.tools.chart_client.httpx.post")
    def test_bad_response_status_propagates_as_http_error(self, mock_post):
        # A reachable service returning an error status is NOT a 503-style
        # outage; it stays an httpx error so callers treat it as a soft failure.
        response = MagicMock()
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "bad request", request=MagicMock(), response=MagicMock()
        )
        mock_post.return_value = response

        with self.assertRaises(httpx.HTTPStatusError):
            get_birth_chart(**_BIRTH)

    @patch("astroweave.common.tools.chart_client.httpx.post")
    def test_successful_call_returns_chart_payload(self, mock_post):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"d1": {"ok": True}}
        mock_post.return_value = response

        self.assertEqual(get_birth_chart(**_BIRTH), {"d1": {"ok": True}})


if __name__ == "__main__":
    unittest.main()
