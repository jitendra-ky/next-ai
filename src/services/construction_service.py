"""Service for fetching and classifying construction sites from OpenStreetMap."""

from datetime import UTC, datetime

from geopy.distance import geodesic

from src.services.base_source import BaseSource
from src.services.cso import (
    Activity,
    CommonSourceObject,
    EmissionRate,
    Location,
    Provenance,
    TemporalValidity,
)
from src.services.overpass_service import OverpassService

# g/s per unit of activity, by construction subtype and pollutant.
CONSTRUCTION_EMISSION_FACTORS = {
    "building_construction": {"PM2.5": 0.25, "PM10": 0.60, "CO": 0.03, "NOx": 0.07, "SO2": 0.0},
    "road_construction": {"PM2.5": 1.80, "PM10": 4.00, "CO": 0.30, "NOx": 0.60, "SO2": 0.0},
    "rail_construction": {"PM2.5": 2.00, "PM10": 4.50, "CO": 0.35, "NOx": 0.70, "SO2": 0.0},
    "area_construction": {"PM2.5": 1.50, "PM10": 3.50, "CO": 0.15, "NOx": 0.30, "SO2": 0.0},
    "general_construction": {"PM2.5": 0.80, "PM10": 1.80, "CO": 0.10, "NOx": 0.20, "SO2": 0.0},
}

# Fallback size_index for subtypes with no numeric OSM attribute.
DEFAULT_SIZE_INDEX = {
    "road_construction": 8,
    "rail_construction": 8,
    "area_construction": 6,
    "general_construction": 4,
}


class ConstructionService(BaseSource):
    """Fetches construction site data from Overpass API and classifies by confidence."""

    def __init__(self) -> None:
        """Initialize with Overpass API client."""
        self.api = OverpassService()

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

    @staticmethod
    def _classify_construction_subtype(tags: dict) -> str:
        """Priority order matters: a way can carry several construction-ish tags at once."""
        if tags.get("railway") == "construction" or "construction:railway" in tags:
            return "rail_construction"
        if tags.get("highway") == "construction":
            return "road_construction"
        if tags.get("building") == "construction":
            return "building_construction"
        if tags.get("landuse") == "construction":
            return "area_construction"
        return "general_construction"

    @staticmethod
    def _get_activity(subtype: str, tags: dict) -> Activity:
        if subtype == "building_construction":
            levels_raw = tags.get("building:levels", "3")
            levels = int(levels_raw) if str(levels_raw).isdigit() else 3
            return Activity(metric="building_levels", value=levels, unit="storeys")

        size_index = DEFAULT_SIZE_INDEX.get(subtype, 4)
        return Activity(
            metric="size_index",
            value=size_index,
            unit="storeys_equivalent (assumed)",
        )

    def to_cso(
        self,
        raw_site: dict,
        retrieved_at: str | None = None,
    ) -> CommonSourceObject:
        """Convert a raw construction site record into a Common Source Object (CSO).

        Args:
        ----
            raw_site: The local site representation returned by get_sites().
            retrieved_at: Optional ISO 8601 timestamp string for provenance.

        Returns:
        -------
            A standardized CSO dataclass instance representing the construction site.

        """
        tags = raw_site.get("tags", {}) or {}
        subtype = self._classify_construction_subtype(tags)
        activity = self._get_activity(subtype, tags)
        factors = CONSTRUCTION_EMISSION_FACTORS[subtype]

        emission_profile = {
            pollutant: EmissionRate(
                rate_gs=round(factors[pollutant] * activity.value, 4),
                method="illustrative_factor",
                factor_source=f"placeholder factor for {subtype} (replace with EPA AP-42 / CPCB)",
                confidence="low",
            )
            for pollutant in factors
        }

        return CommonSourceObject(
            source_id=str(raw_site["site_id"]),
            source_type="construction",
            source_subtype=subtype,
            location=Location(
                lat=float(raw_site["lat"]),
                lon=float(raw_site["lon"]),
                geometry_type="point",
            ),
            effective_release_height_m=5,
            activity=activity,
            emission_profile=emission_profile,
            detection_confidence=str(raw_site.get("confidence", "medium")),
            provenance=Provenance(
                data_source="OpenStreetMap (Overpass query)",
                retrieved_at=retrieved_at or datetime.now(UTC).isoformat(),
            ),
            temporal_validity=TemporalValidity(
                valid_from=None,
                valid_until=None,
                note="OSM construction tag has no expiry; treat as active until re-verified",
            ),
            raw_tags=tags,
        )
