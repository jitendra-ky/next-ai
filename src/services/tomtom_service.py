"""Helpers for calling TomTom traffic flow APIs.

This module provides a thin wrapper around the TomTom Flow API to
retrieve current speeds for given coordinates.
"""

import os

import requests

API_KEY = os.getenv("TOMTOM_API_KEY")

BASE_URL = "https://api.tomtom.com/traffic/services/4/" "flowSegmentData/absolute/10/json"


def get_flow(lat: float, lon: float):
    """Query TomTom Flow API for a point and return summarized flow info.

    Args:
    ----
        lat: Latitude of the point to query.
        lon: Longitude of the point to query.

    Returns:
    -------
        A dictionary with keys ``speed``, ``free_speed``, ``travel_time``,
        ``confidence`` and ``road_closed`` when data is available, or
        ``None`` if the API does not return flow information or an error
        occurs.

    """
    params = {
        "key": API_KEY,
        "point": f"{lat},{lon}",
    }

    try:
        r = requests.get(
            BASE_URL,
            params=params,
            timeout=10,
        )

        r.raise_for_status()

        data = r.json()

        if "flowSegmentData" not in data:
            return None

        flow = data["flowSegmentData"]

        return {
            "speed": flow["currentSpeed"],
            "free_speed": flow["freeFlowSpeed"],
            "travel_time": flow["currentTravelTime"],
            "confidence": flow["confidence"],
            "road_closed": flow["roadClosure"],
        }

    except Exception:
        return None
