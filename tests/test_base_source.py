"""Unit tests for BaseSource abstraction and ConstructionService CSO conversion."""

import unittest
from unittest.mock import MagicMock, patch

import pytest

from src.services.base_source import BaseSource
from src.services.construction_service import ConstructionService
from src.services.cso import (
    Activity,
    CommonSourceObject,
    Location,
    Provenance,
    TemporalValidity,
)


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
        """Test that ConstructionService.to_cso converts raw site dictionary to CSO dataclass."""
        service = ConstructionService()
        raw_site = {
            "site_id": "way/123",
            "lat": 28.61,
            "lon": 77.21,
            "confidence": "high",
            "source_type": "construction",
            "tags": {"building": "construction", "building:levels": "5"},
        }
        cso = service.to_cso(raw_site, retrieved_at="2026-07-28T00:00:00Z")
        self.assertIsInstance(cso, CommonSourceObject)
        self.assertEqual(cso.source_id, "way/123")
        self.assertEqual(cso.source_type, "construction")
        self.assertEqual(cso.location, Location(lat=28.61, lon=77.21, geometry_type="point"))
        self.assertEqual(cso.detection_confidence, "high")
        self.assertEqual(cso.source_subtype, "building_construction")
        self.assertEqual(cso.effective_release_height_m, 5)
        self.assertEqual(
            cso.activity,
            Activity(metric="building_levels", value=5, unit="storeys"),
        )
        self.assertIn("PM2.5", cso.emission_profile)
        self.assertEqual(cso.emission_profile["PM2.5"].rate_gs, round(0.25 * 5, 4))
        self.assertEqual(
            cso.provenance,
            Provenance(
                data_source="OpenStreetMap (Overpass query)",
                retrieved_at="2026-07-28T00:00:00Z",
            ),
        )
        self.assertIsInstance(cso.temporal_validity, TemporalValidity)
        self.assertEqual(cso.raw_tags, {"building": "construction", "building:levels": "5"})

        # Verify to_dict method
        cso_dict = cso.to_dict()
        self.assertEqual(cso_dict["source_id"], "way/123")
        self.assertEqual(
            cso_dict["location"],
            {"lat": 28.61, "lon": 77.21, "geometry_type": "point"},
        )
        self.assertEqual(cso_dict["source_subtype"], "building_construction")
        self.assertEqual(
            cso_dict["activity"],
            {"metric": "building_levels", "value": 5, "unit": "storeys"},
        )
        self.assertEqual(cso_dict["emission_profile"]["PM2.5"]["rate_gs"], 1.25)
        self.assertEqual(
            cso_dict["provenance"],
            {
                "data_source": "OpenStreetMap (Overpass query)",
                "retrieved_at": "2026-07-28T00:00:00Z",
            },
        )

    @patch.object(ConstructionService, "get_sites")
    def test_get_cso_sites(self, mock_get_sites: MagicMock):
        """Test that get_cso_sites returns a list of CSO dataclass instances."""
        mock_get_sites.return_value = [
            {
                "site_id": "node/456",
                "lat": 28.62,
                "lon": 77.22,
                "confidence": "medium",
                "source_type": "construction",
                "tags": {"highway": "construction"},
            }
        ]
        service = ConstructionService()
        cso_list = service.get_cso_sites(28.61, 77.21, radius_km=5)

        mock_get_sites.assert_called_once_with(28.61, 77.21, 5)
        self.assertEqual(len(cso_list), 1)
        self.assertIsInstance(cso_list[0], CommonSourceObject)
        self.assertEqual(cso_list[0].source_id, "node/456")
        self.assertEqual(
            cso_list[0].location,
            Location(lat=28.62, lon=77.22, geometry_type="point"),
        )
        self.assertEqual(cso_list[0].detection_confidence, "medium")
        self.assertEqual(cso_list[0].source_subtype, "road_construction")
