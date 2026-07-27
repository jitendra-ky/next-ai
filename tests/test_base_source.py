"""Unit tests for BaseSource abstraction and ConstructionService CSO conversion (Phase 1)."""

import unittest
from unittest.mock import MagicMock, patch

import pytest

from src.services.base_source import BaseSource
from src.services.construction_service import ConstructionService


class TestBaseSourceAndCSO(unittest.TestCase):
    """Test suite for BaseSource abstraction and ConstructionService CSO conversion."""

    def test_cannot_instantiate_base_source(self):
        """Test that BaseSource cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseSource()

    def test_construction_service_inherits_base_source(self):
        """Test that ConstructionService inherits from BaseSource."""
        service = ConstructionService()
        self.assertIsInstance(service, BaseSource)

    def test_to_cso_conversion(self):
        """Test that ConstructionService.to_cso converts raw site dictionary to CSO dict."""
        service = ConstructionService()
        raw_site = {
            "site_id": "way/123",
            "lat": 28.61,
            "lon": 77.21,
            "confidence": "high",
            "distance_km": 1.5,
            "source_type": "construction",
            "tags": {"landuse": "construction"},
        }
        cso = service.to_cso(raw_site)
        self.assertEqual(cso["source_id"], "way/123")
        self.assertEqual(cso["source_type"], "construction")
        self.assertEqual(cso["location"], {"lat": 28.61, "lon": 77.21})
        self.assertEqual(cso["detection_confidence"], "high")
        self.assertEqual(cso["distance_km"], 1.5)
        self.assertEqual(cso["raw_tags"], {"landuse": "construction"})

    @patch.object(ConstructionService, "get_sites")
    def test_get_cso_sites(self, mock_get_sites: MagicMock):
        """Test that get_cso_sites fetches raw sites and returns a list of CSO dictionaries."""
        mock_get_sites.return_value = [
            {
                "site_id": "node/456",
                "lat": 28.62,
                "lon": 77.22,
                "confidence": "medium",
                "distance_km": 2.0,
                "source_type": "construction",
                "tags": {"man_made": "quarry"},
            }
        ]
        service = ConstructionService()
        cso_list = service.get_cso_sites(28.61, 77.21, radius_km=5)

        mock_get_sites.assert_called_once_with(28.61, 77.21, 5)
        self.assertEqual(len(cso_list), 1)
        self.assertEqual(cso_list[0]["source_id"], "node/456")
        self.assertEqual(cso_list[0]["location"], {"lat": 28.62, "lon": 77.22})
        self.assertEqual(cso_list[0]["detection_confidence"], "medium")
