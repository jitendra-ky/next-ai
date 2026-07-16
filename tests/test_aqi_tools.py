"""Unit tests for `src.aqi_tools`.

These tests verify the geocoding tool behavior under common scenarios.
"""

import unittest
from unittest.mock import MagicMock, Mock, patch

from src.aqi_tools import geocode_place


class TestAQITools(unittest.TestCase):
    """Test suite for AQI Tools using OOP (unittest framework)."""

    def setUp(self):
        """Set up any required state before each test runs."""
        # For this tool, we don't need much setup, but this is where
        # class-level instantiation would go in an OOP structure.

    @patch("src.aqi_tools.requests.get")
    def test_geocode_place_success(self, mock_get: MagicMock):
        """To test the src.api_tools.geocode_place function with a successful response."""
        # Create a mock response object
        mock_response = Mock()
        mock_response.json.return_value = [{"lat": "40.7128", "lon": "-74.0060"}]
        mock_get.return_value = mock_response

        # Call the tool
        result = geocode_place.invoke({"place_name": "New York"})

        # Assert the mock was called with expected URL
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], "https://nominatim.openstreetmap.org/search")
        self.assertEqual(kwargs["params"]["q"], "New York")

        # Assert the returned dictionary matches expectations
        self.assertEqual(
            result,
            {
                "place_name": "New York",
                "latitude": 40.7128,
                "longitude": -74.0060,
            },
        )

    @patch("src.aqi_tools.requests.get")
    def test_geocode_place_not_found(self, mock_get: MagicMock):
        """To test the src.api_tools.geocode_place function with a not found response."""
        # Create a mock response object returning empty list
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        # Call the tool
        result = geocode_place.invoke({"place_name": "UnknownPlace"})

        # Assert the error dictionary is returned
        self.assertEqual(result, {"error": "Could not geocode 'UnknownPlace'"})
