"""Abstract base class for all pollutant sources in the platform."""

from abc import ABC, abstractmethod
from typing import Any

from src.services.cso import CommonSourceObject


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
    def to_cso(
        self,
        raw_site: Any,  # noqa: ANN401
        retrieved_at: str | None = None,
    ) -> CommonSourceObject:
        """Convert a local/raw source object into a Common Source Object (CSO) dataclass.

        Args:
        ----
            raw_site: The local source representation returned by get_sites().
            retrieved_at: Optional ISO 8601 timestamp string for provenance.

        Returns:
        -------
            A standardized CSO dataclass instance representing the source.

        """

    def get_cso_sites(
        self,
        lat: float,
        lon: float,
        radius_km: float = 3,
        retrieved_at: str | None = None,
    ) -> list[CommonSourceObject]:
        """Fetch all sources in a circular area and return them as Common Source Objects (CSOs).

        Args:
        ----
            lat: Latitude of the center point.
            lon: Longitude of the center point.
            radius_km: Search radius in kilometers (default 3).
            retrieved_at: Optional ISO 8601 timestamp string for provenance.

        Returns:
        -------
            List of standardized CSO dataclass instances for all sources found in the area.

        """
        raw_sites = self.get_sites(lat, lon, radius_km)
        return [self.to_cso(site, retrieved_at=retrieved_at) for site in raw_sites]
