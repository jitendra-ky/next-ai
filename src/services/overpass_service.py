"""Overpass API client for fetching OSM construction data."""

import logging

import requests

logger = logging.getLogger(__name__)


class OverpassService:
    """Client for querying the Overpass API with mirror fallback."""

    MIRRORS = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    ]

    HEADERS = {"User-Agent": "AQI-Hackathon-Prototype/1.0"}

    @classmethod
    def fetch_construction_elements(
        cls,
        lat: float,
        lon: float,
        radius_km: float,
        timeout: int = 60,
    ) -> list[dict]:
        """Fetch construction-tagged OSM elements near a location.

        Args:
            lat: Latitude of the center point.
            lon: Longitude of the center point.
            radius_km: Search radius in kilometers.
            timeout: Overpass API timeout in seconds.

        Returns:
            List of OSM element dicts matching construction queries.

        """
        query = f"""
        [out:json][timeout:{timeout}];
        (
          node["landuse"="construction"](around:{radius_km * 1000},{lat},{lon});
          way["landuse"="construction"](around:{radius_km * 1000},{lat},{lon});
          node["building"="construction"](around:{radius_km * 1000},{lat},{lon});
          way["building"="construction"](around:{radius_km * 1000},{lat},{lon});
          way["construction"](around:{radius_km * 1000},{lat},{lon});
        );
        out center tags;
        """

        for mirror in cls.MIRRORS:
            try:
                response = requests.post(
                    mirror,
                    data={"data": query},
                    headers=cls.HEADERS,
                    timeout=timeout,
                )
                response.raise_for_status()
                return response.json()["elements"]
            except Exception:
                logger.warning("Overpass mirror %s failed, trying next", mirror)
                continue

        return []
