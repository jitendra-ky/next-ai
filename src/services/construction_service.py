"""Service for fetching and classifying construction sites from OpenStreetMap."""

from geopy.distance import geodesic

from src.services.overpass_service import OverpassService


class ConstructionService:
    """Fetches construction site data from Overpass API and classifies by confidence."""

    def __init__(self) -> None:
        """Initialize with Overpass API client."""
        self.api = OverpassService()

    @staticmethod
    def classify(tags: dict) -> str | None:
        """Classify a construction site's confidence level based on OSM tags.

        Args:
            tags: OSM element tags dictionary.

        Returns:
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
            lat: Latitude of the center point.
            lon: Longitude of the center point.
            radius_km: Search radius in kilometers (default 3).

        Returns:
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
