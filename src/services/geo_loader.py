"""Load ward polygons from bundled geojson data.

This module exposes helpers for loading ward geometries used by
other services in the project.
"""

from pathlib import Path

import geopandas as gpd

DATA = Path(__file__).parent.parent / "data" / "wards_lucknow.geojson"


class WardPolygonLoader:
    """Load ward polygons on demand from the bundled geojson file."""

    def __init__(self, data_path: Path | None = None) -> None:
        """Initialize the loader."""
        self.data_path = data_path or DATA
        self._wards = None

    def _load_wards(self) -> gpd.GeoDataFrame:
        try:
            return gpd.read_file(self.data_path)
        except Exception as exc:
            msg = f"Unable to load ward data from {self.data_path}"
            raise RuntimeError(
                msg,
            ) from exc

    @property
    def wards(self) -> gpd.GeoDataFrame:
        """Return the loaded ward polygons."""
        if self._wards is None:
            self._wards = self._load_wards()

        return self._wards

    def get_polygon(self, ward_no: int):
        """Return the polygon geometry for a ward number."""
        ward = self.wards[self.wards["Ward Num"] == ward_no]

        if ward.empty:
            raise ValueError("Ward not found")

        return ward.geometry.iloc[0]


_DEFAULT_LOADER = WardPolygonLoader()


def get_polygon(ward_no: int):
    """Return the polygon geometry for a ward number."""
    return _DEFAULT_LOADER.get_polygon(ward_no)
