"""Unit tests for fire detection service and tool."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import requests as req

from src.fire_tools import fire_detection_tool
from src.services.fire_service import FireDetectionService

# FIRMS CSV column headers shared across test fixtures
_CSV_HEADER = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,"
    "acq_time,satellite,confidence,version,bright_t31,frp,daynight"
)


def _csv_rows(*rows: str) -> str:
    """Build a fake FIRMS CSV response from header + data rows."""
    return "\n".join([_CSV_HEADER, *rows, ""])


_SAMPLE_FIRMS_CSV = _csv_rows(
    "28.6139,77.2090,320.5,1.0,1.0,2025-07-20,0345,N,high,2.0,298.1,45.2,D",
    "28.6200,77.2150,310.2,1.2,1.1,2025-07-20,0345,N,nom,2.0,295.0,22.8,D",
    "28.6050,77.1980,305.8,0.8,0.9,2025-07-20,0345,N,low,2.0,290.5,8.1,D",
)

_EMPTY_FIRMS_CSV = _csv_rows()


class TestFireDetectionService(unittest.TestCase):
    """Tests for the FireDetectionService class."""

    def setUp(self) -> None:
        self.service = FireDetectionService(api_key="test_key_123")

    # -- Constructor -------------------------------------------------------

    def test_init_with_explicit_key(self) -> None:
        svc = FireDetectionService(api_key="abc")
        self.assertIsNotNone(svc)

    @patch.dict("os.environ", {"FIRMS_API_KEY": "env_key"})
    def test_init_from_env_var(self) -> None:
        svc = FireDetectionService()
        self.assertIsNotNone(svc)

    def test_raises_without_key_at_call_time(self) -> None:
        with (
            patch.dict("os.environ", {}, clear=True),
            self.assertRaises(ValueError),
        ):
            FireDetectionService().get_fires(28.61, 77.21)

    # -- CSV parsing -------------------------------------------------------

    @patch("src.services.fire_service.requests.get")
    def test_get_fires_returns_parsed_list(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.text = _SAMPLE_FIRMS_CSV
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        fires = self.service.get_fires(28.61, 77.21, 10.0)

        self.assertEqual(len(fires), 3)

        first = fires[0]
        self.assertIn("fire_id", first)
        self.assertEqual(first["lat"], 28.6139)
        self.assertEqual(first["lon"], 77.2090)
        self.assertEqual(first["frp_mw"], 45.2)
        self.assertEqual(first["confidence_pct"], 90)
        self.assertEqual(first["brightness_k"], 320.5)
        self.assertEqual(first["scan"], 1.0)
        self.assertEqual(first["track"], 1.0)
        self.assertEqual(first["daynight"], "D")
        self.assertEqual(first["acq_date"], "2025-07-20")
        self.assertEqual(first["satellite"], "N")
        self.assertEqual(first["source_type"], "fire")

    @patch("src.services.fire_service.requests.get")
    def test_confidence_mapping(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.text = _SAMPLE_FIRMS_CSV
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        fires = self.service.get_fires(28.61, 77.21)

        confidences = [f["confidence_pct"] for f in fires]
        self.assertIn(90, confidences)   # "high"
        self.assertIn(70, confidences)   # "nom"
        self.assertIn(30, confidences)   # "low"

    @patch("src.services.fire_service.requests.get")
    def test_empty_response_returns_empty_list(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.text = ""
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        self.assertEqual(self.service.get_fires(28.61, 77.21), [])

    @patch("src.services.fire_service.requests.get")
    def test_csv_header_only_returns_empty_list(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.text = _EMPTY_FIRMS_CSV
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        self.assertEqual(self.service.get_fires(28.61, 77.21), [])

    @patch("src.services.fire_service.requests.get")
    def test_api_error_returns_empty_list(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = req.ConnectionError("connection refused")

        self.assertEqual(self.service.get_fires(28.61, 77.21), [])

    @patch("src.services.fire_service.requests.get")
    def test_401_error_returns_empty_list(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req.HTTPError(
            response=MagicMock(status_code=401),
        )
        mock_get.return_value = mock_resp

        self.assertEqual(self.service.get_fires(28.61, 77.21), [])

    @patch("src.services.fire_service.requests.get")
    def test_radius_is_clamped(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.text = _EMPTY_FIRMS_CSV
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        self.service.get_fires(28.61, 77.21, radius_km=500.0)

        call_url = mock_get.call_args[0][0]
        # Bounding box should be clamped to ~300km, not 500km
        self.assertIn("/5", call_url)  # days param is last

    @patch("src.services.fire_service.requests.get")
    def test_api_url_contains_bbox(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.text = _EMPTY_FIRMS_CSV
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        self.service.get_fires(28.61, 77.21, 5.0)

        call_url = mock_get.call_args[0][0]
        # URL format: .../SOURCE/WEST,SOUTH,EAST,NORTH/DAYS
        parts = call_url.split("/")
        bbox_part = parts[-2]  # "west,south,east,north"
        coords = bbox_part.split(",")
        self.assertEqual(len(coords), 4)
        # west < lon < east, south < lat < north
        self.assertLess(float(coords[0]), 77.21)
        self.assertGreater(float(coords[2]), 77.21)
        self.assertLess(float(coords[1]), 28.61)
        self.assertGreater(float(coords[3]), 28.61)

    @patch("src.services.fire_service.requests.get")
    def test_malformed_rows_are_skipped(self, mock_get: MagicMock) -> None:
        bad_csv = _csv_rows(
            "not_a_number,77.2090,320.5,1.0,1.0,2025-07-20,0345,N,high,2.0,298.1,45.2,D",
            "28.6200,77.2150,310.2,1.2,1.1,2025-07-20,0345,N,nom,2.0,295.0,22.8,D",
        )
        mock_resp = MagicMock()
        mock_resp.text = bad_csv
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        fires = self.service.get_fires(28.61, 77.21)

        self.assertEqual(len(fires), 1)
        self.assertEqual(fires[0]["lat"], 28.6200)

    @patch("src.services.fire_service.requests.get")
    def test_fire_ids_are_unique(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.text = _SAMPLE_FIRMS_CSV
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        fires = self.service.get_fires(28.61, 77.21)

        ids = [f["fire_id"] for f in fires]
        self.assertEqual(len(ids), len(set(ids)))


class TestFireDetectionTool(unittest.TestCase):
    """Tests for the LangChain tool wrapper."""

    @patch("src.fire_tools._fire_service")
    def test_tool_returns_fire_list(self, mock_svc: MagicMock) -> None:
        mock_svc.get_fires.return_value = [
            {
                "fire_id": "firms_28.61_77.21_0",
                "lat": 28.61,
                "lon": 77.21,
                "frp_mw": 45.2,
                "confidence_pct": 90,
                "brightness_k": 320.5,
                "scan": 1.0,
                "track": 1.0,
                "daynight": "D",
                "acq_date": "2025-07-20",
                "acq_time": "0345",
                "satellite": "N",
                "source_type": "fire",
            }
        ]

        result = fire_detection_tool.invoke(
            {"lat": 28.61, "lon": 77.21, "radius_km": 10.0},
        )

        mock_svc.get_fires.assert_called_once_with(28.61, 77.21, 10.0)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["fire_id"], "firms_28.61_77.21_0")

    @patch("src.fire_tools._fire_service")
    def test_tool_empty_results(self, mock_svc: MagicMock) -> None:
        mock_svc.get_fires.return_value = []

        result = fire_detection_tool.invoke(
            {"lat": 28.61, "lon": 77.21, "radius_km": 10.0},
        )

        self.assertEqual(result, [])

    @patch("src.fire_tools._fire_service")
    def test_tool_default_radius(self, mock_svc: MagicMock) -> None:
        mock_svc.get_fires.return_value = []

        fire_detection_tool.invoke({"lat": 28.61, "lon": 77.21})

        mock_svc.get_fires.assert_called_once_with(28.61, 77.21, 10.0)


if __name__ == "__main__":
    unittest.main()
