"""Service for fetching and classifying construction sites from OpenStreetMap."""

# ruff: noqa: I001
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from geopy.distance import geodesic

from services.overpass_service import OverpassService


class ConstructionStrategy(ABC):
    """Abstract base class for construction site strategies."""

    @property
    @abstractmethod
    def subtype(self) -> str:
        """Get the construction subtype."""

    @property
    @abstractmethod
    def emission_factors(self) -> dict:
        """Get the emission factors for this subtype."""

    @abstractmethod
    def get_activity(self, tags: dict) -> dict:
        """Calculate the activity metric based on tags."""


class BuildingConstructionStrategy(ConstructionStrategy):
    """Strategy for building construction sites."""

    @property
    def subtype(self) -> str:
        """Get the subtype for building construction."""
        return "building_construction"

    @property
    def emission_factors(self) -> dict:
        """Get the emission factors for building construction."""
        return {"PM2.5": 0.25, "PM10": 0.60, "CO": 0.03, "NOx": 0.07, "SO2": 0.0}

    def get_activity(self, tags: dict) -> dict:
        """Calculate the activity metric based on building levels from tags."""
        levels_raw = tags.get("building:levels", "3")
        levels = int(levels_raw) if str(levels_raw).isdigit() else 3
        return {"metric": "building_levels", "value": levels, "unit": "storeys"}


class DefaultConstructionStrategy(ConstructionStrategy):
    """Fallback strategy for subtypes with no numeric OSM attribute."""

    def __init__(self, subtype: str, factors: dict, default_size: int) -> None:
        """Initialize the default construction strategy."""
        self._subtype = subtype
        self._factors = factors
        self._default_size = default_size

    @property
    def subtype(self) -> str:
        """Get the subtype for this default strategy."""
        return self._subtype

    @property
    def emission_factors(self) -> dict:
        """Get the emission factors for this default strategy."""
        return self._factors

    def get_activity(self, _tags: dict) -> dict:
        """Calculate the default activity metric."""
        return {
            "metric": "size_index",
            "value": self._default_size,
            "unit": "storeys_equivalent (assumed)",
        }


class ConstructionStrategyFactory:
    """Factory to determine the construction strategy from OSM tags."""

    @staticmethod
    def get_strategy(tags: dict) -> ConstructionStrategy:
        """Priority order matters: a way can carry several construction-ish tags at once."""
        if tags.get("railway") == "construction" or "construction:railway" in tags:
            return DefaultConstructionStrategy(
                "rail_construction",
                {"PM2.5": 2.00, "PM10": 4.50, "CO": 0.35, "NOx": 0.70, "SO2": 0.0},
                8,
            )
        if tags.get("highway") == "construction":
            return DefaultConstructionStrategy(
                "road_construction",
                {"PM2.5": 1.80, "PM10": 4.00, "CO": 0.30, "NOx": 0.60, "SO2": 0.0},
                8,
            )
        if tags.get("building") == "construction":
            return BuildingConstructionStrategy()
        if tags.get("landuse") == "construction":
            return DefaultConstructionStrategy(
                "area_construction",
                {"PM2.5": 1.50, "PM10": 3.50, "CO": 0.15, "NOx": 0.30, "SO2": 0.0},
                6,
            )
        return DefaultConstructionStrategy(
            "general_construction",
            {"PM2.5": 0.80, "PM10": 1.80, "CO": 0.10, "NOx": 0.20, "SO2": 0.0},
            4,
        )


class ConstructionCSOConverter:
    """Converts a raw OSM-derived construction-site record into a Common Source Object (CSO)."""

    def __init__(self, factory: ConstructionStrategyFactory | None = None) -> None:
        """Initialize with an optional ConstructionStrategyFactory."""
        self.factory = factory or ConstructionStrategyFactory()

    def convert(self, raw_site: dict, retrieved_at: str | None = None) -> dict:
        """Convert one raw construction-site record into a Common Source Object."""
        tags = raw_site.get("tags", {}) or {}
        strategy = self.factory.get_strategy(tags)
        subtype = strategy.subtype
        activity = strategy.get_activity(tags)
        factors = strategy.emission_factors

        emission_profile = {
            pollutant: {
                "rate_gs": round(factors[pollutant] * activity["value"], 4),
                "method": "illustrative_factor",
                "factor_source": (
                    f"placeholder factor for {subtype} (replace with EPA AP-42 / CPCB)"
                ),
                "confidence": "low",
            }
            for pollutant in factors
        }

        return {
            "source_id": raw_site.get("site_id"),
            "source_type": "construction",
            "source_subtype": subtype,
            "location": {
                "lat": raw_site.get("lat"),
                "lon": raw_site.get("lon"),
                "geometry_type": "point",
            },
            "effective_release_height_m": 5,
            "activity": activity,
            "emission_profile": emission_profile,
            "detection_confidence": raw_site.get("confidence", "medium"),
            "provenance": {
                "data_source": "OpenStreetMap (Overpass query)",
                "retrieved_at": retrieved_at or datetime.now(UTC).isoformat(),
            },
            "temporal_validity": {
                "valid_from": None,
                "valid_until": None,
                "note": "OSM construction tag has no expiry; treat as active until re-verified",
            },
            "raw_tags": tags,
        }

    def convert_batch(self, raw_sites: list[dict], retrieved_at: str | None = None) -> list[dict]:
        """Convert a whole list of raw construction records."""
        return [self.convert(s, retrieved_at=retrieved_at) for s in raw_sites]


class ConstructionService:
    """Fetches construction site data from Overpass API and classifies by confidence."""

    def __init__(self) -> None:
        """Initialize with Overpass API client and CSO converter."""
        self.api = OverpassService()
        self.cso_converter = ConstructionCSOConverter()

    @staticmethod
    def classify(tags: dict) -> str | None:
        """Classify a construction site's confidence level based on OSM tags.

        Args:
        ----
            tags: OSM element tags dictionary.

        Returns:
        -------
            "high" for active construction zones, "medium" for quarries/construction
            tagged areas, or None if not a construction site.

        """
        if tags.get("landuse") == "construction" or tags.get("building") == "construction":
            return "high"

        if (
            "construction" in tags
            or tags.get("landuse") == "quarry"
            or tags.get("man_made") == "quarry"
        ):
            return "medium"

        return None

    def get_sites(
        self,
        lat: float,
        lon: float,
        radius_km: float = 3,
    ) -> list[dict]:
        """Fetch construction sites near a location.

        Args:
        ----
            lat: Latitude of the center point.
            lon: Longitude of the center point.
            radius_km: Search radius in kilometers (default 3).

        Returns:
        -------
            List of dicts with site_id, lat, lon, confidence, distance_km,
            source_type, and tags for each construction site found.

        """
        elements = self.api.fetch_construction_elements(
            lat,
            lon,
            radius_km,
        )

        sites = []

        for element in elements:
            tags = element.get("tags", {})

            confidence = self.classify(tags)

            if confidence is None:
                continue

            site_lat = element.get("lat") or element.get("center", {}).get("lat")

            site_lon = element.get("lon") or element.get("center", {}).get("lon")

            if site_lat is None or site_lon is None:
                continue

            distance = geodesic(
                (lat, lon),
                (site_lat, site_lon),
            ).km

            sites.append(
                {
                    "site_id": f"{element.get('type')}/{element.get('id')}",
                    "lat": site_lat,
                    "lon": site_lon,
                    "confidence": confidence,
                    "distance_km": round(distance, 3),
                    "source_type": "construction",
                    "tags": tags,
                }
            )

        return sites

    def get_cso_sites(
        self,
        lat: float,
        lon: float,
        radius_km: float = 3,
    ) -> list[dict]:
        """Fetch construction sites near a location and return as CSO objects.

        Args:
        ----
            lat: Latitude of the center point.
            lon: Longitude of the center point.
            radius_km: Search radius in kilometers (default 3).

        Returns:
        -------
            List of dicts representing Common Source Objects (CSO).

        """
        raw_sites = self.get_sites(lat, lon, radius_km)
        return self.cso_converter.convert_batch(raw_sites)
