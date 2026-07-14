"""Load ward polygons from bundled geojson data.

This module exposes helpers for loading ward geometries used by
other services in the project.
"""

from pathlib import Path

import geopandas as gpd

DATA = Path(__file__).parent.parent / "data" / "wards_lucknow.geojson"

wards = gpd.read_file(DATA)


def get_polygon(ward_no: int):
    """Return the polygon geometry for a ward number.

    Args:
        ward_no: The ward number to look up.

    Returns:
        A ``shapely.geometry`` Polygon representing the ward boundary.

    Raises:
        ValueError: If the ward number cannot be found in the dataset.

    """
    ward = wards[wards["Ward Num"] == ward_no]

    if ward.empty:
        raise ValueError("Ward not found")

    return ward.geometry.iloc[0]
