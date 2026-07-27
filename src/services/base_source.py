"""Abstract base class for all pollutant sources in the platform."""

from abc import ABC, abstractmethod
from typing import Any


class BaseSource(ABC):
    """Abstract base class providing a unified interface for detecting pollutant sources.

    All specific source services (e.g., Construction, Fire) must inherit from this class
    and implement methods to detect local sources and convert them to Common Source
    Objects (CSOs).
    """

    @abstractmethod
    def get_sites(
        self,
        lat: float,
        lon: float,
        radius_km: float = 3,
    ) -> list[Any]:
        """Find all sources of this particular type within a given circular area.

        Args:
        ----
            lat: Latitude of the center point.
            lon: Longitude of the center point.
            radius_km: Search radius in kilometers (default 3).

        Returns:
        -------
            List of local/raw source objects or dictionaries found in the area.

        """

    @abstractmethod
    def to_cso(self, raw_site: Any) -> dict:  # noqa: ANN401
        """Convert a local/raw source object into a Common Source Object (CSO) dictionary.

        Args:
        ----
            raw_site: The local source representation returned by get_sites().

        Returns:
        -------
            A standardized CSO dictionary representing the source.

        """

    def get_cso_sites(
        self,
        lat: float,
        lon: float,
        radius_km: float = 3,
    ) -> list[dict]:
        """Fetch all sources in a circular area and return them as Common Source Objects (CSOs).

        Args:
        ----
            lat: Latitude of the center point.
            lon: Longitude of the center point.
            radius_km: Search radius in kilometers (default 3).

        Returns:
        -------
            List of standardized CSO dictionaries for all sources found in the area.

        """
        raw_sites = self.get_sites(lat, lon, radius_km)
        return [self.to_cso(site) for site in raw_sites]
