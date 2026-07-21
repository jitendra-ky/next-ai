"""Fire detection data service using NASA FIRMS API.

Fetches active fire/hotspot detections near a geographic point using the
VIIRS sensor (Suomi NPP, 375m resolution, near-real-time).

API docs: https://firms.modaps.eosdis.nasa.gov/api/area/

Requires FIRMS_API_KEY env var. Get a free key at:
  https://firms.modaps.eosdis.nasa.gov/api/area/
"""

from __future__ import annotations

import csv
import io
import logging
import math
import os

import requests

logger = logging.getLogger(__name__)

FIRMS_API_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
DEFAULT_SOURCE = "VIIRS_SNPP_NRT"
DEFAULT_RADIUS_KM = 10.0
DEFAULT_DAYS = 5
REQUEST_TIMEOUT_S = 20

# FIRMS confidence strings -> numeric percentage
_CONFIDENCE_MAP = {
    "low": 30,
    "nom": 70,
    "nominal": 70,
    "high": 90,
}


class FireDetectionService:
    """Fetches and parses fire detection data from the NASA FIRMS API."""

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize with an explicit key or fall back to the FIRMS_API_KEY env var.

        Args:
            api_key: NASA FIRMS map key.  If *None*, reads ``FIRMS_API_KEY``
                from the process environment.

        Raises:
            ValueError: If no API key is available at call time.

        """
        self._api_key = api_key or os.environ.get("FIRMS_API_KEY", "")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_fires(
        self,
        lat: float,
        lon: float,
        radius_km: float = DEFAULT_RADIUS_KM,
        *,
        source: str = DEFAULT_SOURCE,
        days: int = DEFAULT_DAYS,
    ) -> list[dict]:
        """Fetch active fire detections near a point from NASA FIRMS.

        Args:
            lat: Latitude of the search center.
            lon: Longitude of the search center.
            radius_km: Search radius in kilometres (clamped to 300).
            source: FIRMS data source identifier (default VIIRS_SNPP_NRT).
            days: Number of past days to query (1-5, clamped).

        Returns:
            List of fire detection dicts with fire_id, lat, lon, frp_mw,
            confidence_pct, brightness_k, scan, track, daynight, acq_date.

        Raises:
            ValueError: If no API key is available.

        """
        if not self._api_key:
            raise ValueError(
                "FIRMS_API_KEY environment variable is not set. "
                "Get a free key at https://firms.modaps.eosdis.nasa.gov/api/area/"
            )
        clamped_days = max(1, min(days, 5))
        clamped_radius = min(max(radius_km, 0.1), 300.0)

        url = self._build_url(lat, lon, clamped_radius, source, clamped_days)

        text = self._fetch_csv(url)
        if not text:
            return []

        return self._parse_csv(text)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_url(
        self,
        lat: float,
        lon: float,
        radius_km: float,
        source: str,
        days: int,
    ) -> str:
        """Build the FIRMS area CSV download URL."""
        west, south, east, north = self._bbox_from_center(lat, lon, radius_km)
        area = f"{west},{south},{east},{north}"
        return f"{FIRMS_API_URL}/{self._api_key}/{source}/{area}/{days}"

    def _fetch_csv(self, url: str) -> str:
        """Download CSV text from *url*, returning empty string on failure."""
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT_S)
            resp.raise_for_status()
        except requests.RequestException:
            logger.exception("FIRMS API request failed")
            return ""
        return resp.text.strip()

    def _parse_csv(self, text: str) -> list[dict]:
        """Parse a FIRMS CSV response body into a list of fire dicts."""
        reader = csv.DictReader(io.StringIO(text))
        fires: list[dict] = []

        for idx, row in enumerate(reader):
            parsed = self._parse_row(row, idx)
            if parsed is not None:
                fires.append(parsed)

        return fires

    def _parse_row(self, row: dict[str, str], idx: int) -> dict | None:
        """Convert a single CSV row into a fire detection dict.

        Returns *None* for malformed rows so the caller can skip them.
        """
        try:
            fire_lat = float(row.get("latitude", 0))
            fire_lon = float(row.get("longitude", 0))
            frp = float(row.get("frp", 0.0))
            brightness = float(row.get("bright_ti4", row.get("bright_t31", 0.0)))
            scan_val = float(row.get("scan", 1.0))
            track_val = float(row.get("track", 1.0))
        except (ValueError, KeyError):
            logger.warning("Skipping malformed FIRMS row %d: %s", idx, row)
            return None

        return {
            "fire_id": f"firms_{fire_lat}_{fire_lon}_{idx}",
            "lat": fire_lat,
            "lon": fire_lon,
            "frp_mw": round(frp, 2),
            "confidence_pct": self._map_confidence(row.get("confidence", "nom")),
            "brightness_k": round(brightness, 1),
            "scan": round(scan_val, 2),
            "track": round(track_val, 2),
            "daynight": row.get("daynight", "D"),
            "acq_date": row.get("acq_date", ""),
            "acq_time": row.get("acq_time", ""),
            "satellite": row.get("satellite", ""),
            "source_type": "fire",
        }

    @staticmethod
    def _map_confidence(raw: str) -> int:
        """Map a FIRMS confidence string to a numeric percentage."""
        return _CONFIDENCE_MAP.get(raw.strip().lower(), 50)

    @staticmethod
    def _bbox_from_center(
        lat: float,
        lon: float,
        radius_km: float,
    ) -> tuple[float, float, float, float]:
        """Convert a center point + radius to [west, south, east, north]."""
        dlat = radius_km / 111.0
        dlon = radius_km / (111.0 * math.cos(math.radians(lat)))
        return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)
