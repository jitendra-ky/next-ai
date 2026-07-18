"""High-level traffic aggregation utilities.

This module composes lower-level services to compute ward-level
traffic summaries used by the application and tools.
"""

from typing import Any

from src.services.geo_loader import WardPolygonLoader
from src.services.osm_service import MajorRoadService
from src.services.tomtom_service import TomTomFlowService


class TrafficDataService:
    """Aggregate ward traffic data using lower-level service adapters."""

    def __init__(
        self,
        ward_loader: object = None,
        road_service: object = None,
        flow_service: object = None,
    ) -> None:
        """Initialize the service."""
        self.ward_loader = ward_loader or WardPolygonLoader()
        self.road_service = road_service or MajorRoadService()
        self.flow_service = flow_service or TomTomFlowService()

    def _empty_summary(self, ward_no: int) -> dict[str, Any]:
        return {
            "ward": ward_no,
            "average_speed": 0.0,
            "average_congestion": 0.0,
            "roads": 0,
            "closed_roads": 0,
            "confidence": 0.0,
        }

    def get_traffic_data(self, ward_no: int):
        """Compute aggregated traffic statistics for a ward."""
        polygon = self.ward_loader.get_polygon(ward_no)
        roads = self.road_service.get_major_roads(polygon)

        if roads.empty:
            return self._empty_summary(ward_no)

        speed = []
        free_speed = []
        confidence = []
        road_closed = []

        for row in roads.itertuples():
            flow = self.flow_service.get_flow(row.lat, row.lon)

            if flow is None:
                speed.append(None)
                free_speed.append(None)
                confidence.append(None)
                road_closed.append(None)
                continue

            speed.append(flow["speed"])
            free_speed.append(flow["free_speed"])
            confidence.append(flow["confidence"])
            road_closed.append(flow["road_closed"])

        roads = roads.copy()
        roads["speed"] = speed
        roads["free_speed"] = free_speed
        roads["confidence"] = confidence
        roads["road_closed"] = road_closed
        roads = roads.dropna(subset=["speed", "free_speed", "confidence", "road_closed"])

        if roads.empty:
            return self._empty_summary(ward_no)

        roads["congestion"] = (1 - roads["speed"] / roads["free_speed"]) * 100

        total_length = roads["length"].sum()
        if total_length == 0:
            return self._empty_summary(ward_no)

        avg_speed = (roads["speed"] * roads["length"]).sum() / total_length
        avg_congestion = (roads["congestion"] * roads["length"]).sum() / total_length

        return {
            "ward": ward_no,
            "average_speed": float(round(avg_speed, 2)),
            "average_congestion": float(round(avg_congestion, 2)),
            "roads": len(roads),
            "closed_roads": int(roads["road_closed"].fillna(value=False).sum()),
            "confidence": float(round(roads["confidence"].mean(), 2)),
        }


_DEFAULT_SERVICE = TrafficDataService()


def get_traffic_data(ward_no: int):
    """Compute aggregated traffic statistics for a ward."""
    return _DEFAULT_SERVICE.get_traffic_data(ward_no)
