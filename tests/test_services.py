"""Unit tests for the traffic service layer."""

from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

import pandas as pd

from src.services.geo_loader import WardPolygonLoader, get_polygon
from src.services.osm_service import MajorRoadService
from src.services.tomtom_service import TomTomFlowService
from src.services.traffic_service import TrafficDataService


class TestWardPolygonLoader(TestCase):
    """Validate lazy loading and ward lookup behavior."""

    def test_get_polygon_loads_lazily(self):
        """Test lazy loading of polygons."""
        loader = WardPolygonLoader(data_path=Path("dummy.geojson"))
        frame = pd.DataFrame(
            {
                "Ward Num": [10],
                "geometry": ["polygon-10"],
            },
        )
        loader._load_wards = Mock(return_value=frame)  # noqa: SLF001

        result = loader.get_polygon(10)

        self.assertEqual(result, "polygon-10")

    @patch("src.services.geo_loader._DEFAULT_LOADER")
    def test_module_get_polygon_uses_default_loader(self, default_loader: Mock):
        """Test module uses default loader."""
        default_loader.get_polygon.return_value = "polygon"

        result = get_polygon(7)

        self.assertEqual(result, "polygon")
        default_loader.get_polygon.assert_called_once_with(7)


class TestTomTomFlowService(TestCase):
    """Validate TomTom flow adapter behavior."""

    def test_get_flow_returns_summary(self):
        """Test get flow summary."""
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "flowSegmentData": {
                "@version": 1,
                "currentSpeed": 30,
                "freeFlowSpeed": 50,
                "currentTravelTime": 120,
                "freeFlowTravelTime": 100,
                "confidence": 0.9,
                "roadClosure": False,
                "frc": "FRC2",
                "coordinates": {"coordinate": []},
            },
        }
        http_client = Mock()
        http_client.get.return_value = response
        service = TomTomFlowService(api_key="key", http_client=http_client)

        result = service.get_flow(12.34, 56.78)

        self.assertEqual(
            result,
            {
                "api_version": 1,
                "speed": 30,
                "free_speed": 50,
                "travel_time": 120,
                "free_flow_travel_time": 100,
                "confidence": 0.9,
                "road_closed": False,
                "frc": "FRC2",
                "coordinates": {"coordinate": []},
            },
        )


class TestTrafficDataService(TestCase):
    """Validate orchestration and dependency injection."""

    def test_get_traffic_data_aggregates_results(self):
        """Test aggregating traffic results."""
        ward_loader = Mock()
        road_service = Mock()
        flow_service = Mock()

        ward_loader.get_polygon.return_value = "polygon"
        road_service.get_major_roads.return_value = pd.DataFrame(
            {
                "length": [2.0, 1.0],
                "lat": [10.0, 11.0],
                "lon": [20.0, 21.0],
            },
        )
        flow_service.get_flow.side_effect = [
            {
                "speed": 20,
                "free_speed": 40,
                "travel_time": 100,
                "free_flow_travel_time": 90,
                "confidence": 0.8,
                "road_closed": False,
                "frc": "FRC2",
                "coordinates": {"coordinate": []},
            },
            {
                "speed": 10,
                "free_speed": 20,
                "travel_time": 50,
                "free_flow_travel_time": 45,
                "confidence": 0.6,
                "road_closed": True,
                "frc": "FRC3",
                "coordinates": {"coordinate": []},
            },
        ]

        service = TrafficDataService(
            ward_loader=ward_loader,
            road_service=road_service,
            flow_service=flow_service,
        )

        result = service.get_traffic_data(12)

        self.assertEqual(result["ward"], 12)
        self.assertEqual(result["roads"], 2)
        self.assertEqual(result["closed_roads"], 1)
        self.assertEqual(result["average_speed"], 16.67)
        self.assertEqual(result["average_congestion"], 50.0)
        self.assertEqual(result["confidence"], 0.7)

    def test_empty_road_set_returns_zero_summary(self):
        """Test empty road set returns zero summary."""
        service = TrafficDataService(
            ward_loader=Mock(get_polygon=Mock(return_value="polygon")),
            road_service=Mock(get_major_roads=Mock(return_value=pd.DataFrame())),
            flow_service=Mock(),
        )

        result = service.get_traffic_data(3)

        self.assertEqual(
            result,
            {
                "ward": 3,
                "average_speed": 0.0,
                "average_congestion": 0.0,
                "roads": 0,
                "closed_roads": 0,
                "confidence": 0.0,
            },
        )


class TestMajorRoadService(TestCase):
    """Validate helper behavior in isolation."""

    def test_major_road_helper(self):
        """Test major road helper."""
        service = MajorRoadService()

        self.assertTrue(service._is_major_road(["primary"]))  # noqa: SLF001
        self.assertFalse(service._is_major_road(["residential"]))  # noqa: SLF001
