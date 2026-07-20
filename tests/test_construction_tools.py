"""Unit tests for `src.construction_tools`."""

import unittest
from unittest.mock import MagicMock, patch

from src.construction_tools import construction_tool


class TestConstructionTool(unittest.TestCase):
    """Test suite for Construction Tool."""

    @patch("src.construction_tools.construction_service")
    def test_construction_tool_returns_sites(self, mock_service: MagicMock):
        """Test construction_tool returns sites from service."""
        mock_service.get_sites.return_value = [
            {
                "site_id": "way/123",
                "lat": 28.6139,
                "lon": 77.2090,
                "confidence": "high",
                "distance_km": 1.234,
                "source_type": "construction",
                "tags": {"landuse": "construction"},
            }
        ]

        result = construction_tool.invoke({"lat": 28.61, "lon": 77.21, "radius_km": 3})

        mock_service.get_sites.assert_called_once_with(28.61, 77.21, 3)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["site_id"], "way/123")
        self.assertEqual(result[0]["confidence"], "high")

    @patch("src.construction_tools.construction_service")
    def test_construction_tool_empty_results(self, mock_service: MagicMock):
        """Test construction_tool returns empty list when no sites found."""
        mock_service.get_sites.return_value = []

        result = construction_tool.invoke({"lat": 28.61, "lon": 77.21, "radius_km": 3})

        self.assertEqual(result, [])

    @patch("src.construction_tools.construction_service")
    def test_construction_tool_default_radius(self, mock_service: MagicMock):
        """Test construction_tool uses default radius_km of 3."""
        mock_service.get_sites.return_value = []

        construction_tool.invoke({"lat": 28.61, "lon": 77.21})

        mock_service.get_sites.assert_called_once_with(28.61, 77.21, 3)
