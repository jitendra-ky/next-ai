"""Minimal CAAQMS (OpenAQ) tools for the AQI agent.

Set OPENAQ_API_KEY before use. Get a free key at https://explore.openaq.org.
"""

import os
from datetime import UTC, datetime, timedelta
from statistics import mean

import requests
from langchain_core.tools import tool

BASE_URL = "https://api.openaq.org/v3"
HEADERS = {"X-API-Key": os.environ.get("OPENAQ_API_KEY", "")}


def _get(path: str, params: dict | None = None) -> list:
    resp = requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json().get("results", [])


@tool
def geocode_place(place_name: str) -> dict:
    """Convert a place name (locality, ward, landmark) to latitude/longitude.

    Always call this before find_nearby_stations if you only have a place name.
    """
    resp = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": place_name, "format": "json", "limit": 1},
        headers={"User-Agent": "aqi-agent/1.0"},  # Nominatim requires a UA header
        timeout=10,
    )
    results = resp.json()
    if not results:
        return {"error": f"Could not geocode '{place_name}'"}
    return {
        "place_name": place_name,
        "latitude": float(results[0]["lat"]),
        "longitude": float(results[0]["lon"]),
    }


@tool
def find_nearby_stations(latitude: float, longitude: float, radius_km: float = 5.0) -> dict:
    """Find CAAQMS stations near a point.

    Returns location_id, name, and pollutants measured — use this first to get
    a location_id for the other tools.
    """
    locations = _get("/locations", {
        "coordinates": f"{latitude},{longitude}",
        "radius": int(min(radius_km, 25) * 1000),
        "limit": 25,
    })
    return {
        "stations": [
            {
                "location_id": loc["id"],
                "name": loc.get("name"),
                "parameters_measured": sorted(
                    {s["parameter"]["name"] for s in loc.get("sensors", [])},
                ),
            }
            for loc in locations
        ],
    }


@tool
def get_station_air_quality_snapshot(location_id: int, lookback_hours: int = 6) -> dict:
    """Latest reading per pollutant at a station.

    Includes the % change over the last N hours (rising/falling/stable).
    """
    location = _get(f"/locations/{location_id}")[0]
    latest = {row["sensorsId"]: row for row in _get(f"/locations/{location_id}/latest")}
    since = (datetime.now(UTC) - timedelta(hours=lookback_hours)).isoformat()

    readings = []
    for sensor in location.get("sensors", []):
        sid = sensor["id"]
        row = latest.get(sid)
        if not row:
            continue
        hours = _get(f"/sensors/{sid}/hours", {"datetime_from": since, "limit": 100})
        values = [h["value"] for h in hours if h.get("value") is not None]

        entry = {
            "parameter": sensor["parameter"]["name"],
            "latest_value": row["value"],
        }
        if len(values) >= 2: # noqa: PLR2004
            pct = (values[-1] - values[0]) / values[0] * 100 if values[0] else 0
            entry["percent_change"] = round(pct, 1)
            entry["trend"] = "rising" if pct > 5 else "falling" if pct < -5 else "stable" # noqa: PLR2004
        readings.append(entry)

    return {"location_id": location_id, "station_name": location.get("name"), "readings": readings}


@tool
def get_historical_baseline(location_id: int, parameter: str, days: int = 14) -> dict:
    """Daily-average history for one pollutant at a station over the past N days.

    Returns mean/max/min — grounds 'similar conditions -> AQI X' claims.
    """
    location = _get(f"/locations/{location_id}")[0]
    sensor = next((s for s in location["sensors"] if s["parameter"]["name"] == parameter), None)
    if not sensor:
        return {"error": f"No '{parameter}' sensor at station {location_id}"}

    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    daily = _get(f"/sensors/{sensor['id']}/days", {"datetime_from": since, "limit": 366})
    values = [d["value"] for d in daily if d.get("value") is not None]
    if not values:
        return {"note": "No historical data for this window."}

    return {
        "parameter": parameter,
        "mean": round(mean(values), 1),
        "max": round(max(values), 1),
        "min": round(min(values), 1),
    }


CAAQMS_TOOLS = [
    geocode_place,
    find_nearby_stations,
    get_station_air_quality_snapshot,
    get_historical_baseline,
    ]
