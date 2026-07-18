"""Utilities for extracting road geometries from OpenStreetMap via osmnx.

This module provides helpers to filter and transform road data used
by the traffic analysis tools.
"""

import osmnx as ox
from shapely.geometry import Polygon

MAJOR_ROADS = [
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
]


class MajorRoadService:
    """Extract major roads from an OpenStreetMap road network."""

    def __init__(
        self,
        road_types: list[str] | tuple[str, ...] | None = None,
        osm_client: object = None,
    ) -> None:
        """Initialize the service."""
        self.road_types = tuple(road_types or MAJOR_ROADS)
        self.osm_client = osm_client or ox

    def _is_major_road(self, highway: str | list[str]) -> bool:
        roads = highway if isinstance(highway, list) else [highway]
        return any(road in self.road_types for road in roads)

    def get_major_roads(self, polygon: Polygon):
        """Return a GeoDataFrame of major roads that intersect a polygon."""
        graph = self.osm_client.graph_from_polygon(polygon, network_type="drive")

        _, edges = self.osm_client.graph_to_gdfs(graph)

        roads = edges[edges["highway"].apply(self._is_major_road)].copy()
        roads["midpoint"] = roads.geometry.interpolate(0.5, normalized=True)
        roads["lat"] = roads.midpoint.y
        roads["lon"] = roads.midpoint.x

        return roads


_DEFAULT_SERVICE = MajorRoadService()


def get_major_roads(polygon: Polygon):
    """Return a GeoDataFrame of major roads that intersect a polygon."""
    return _DEFAULT_SERVICE.get_major_roads(polygon)
