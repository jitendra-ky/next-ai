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


def get_major_roads(polygon: Polygon):

    graph = ox.graph_from_polygon(polygon, network_type="drive")

    _, edges = ox.graph_to_gdfs(graph)

    roads = edges[
        edges["highway"].apply(
            lambda x: any(
                road in MAJOR_ROADS
                for road in (x if isinstance(x, list) else [x])
            ),
        )
    ].copy()

    roads["midpoint"] = roads.geometry.interpolate(0.5,normalized=True)

    roads["lat"] = roads.midpoint.y
    roads["lon"] = roads.midpoint.x

    return roads
