"""Helpers for calling TomTom traffic flow APIs.

This module provides a thin wrapper around the TomTom Flow API to
retrieve current speeds for given coordinates.
"""

import os

import requests

BASE_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"


class TomTomFlowService:
    """Query the TomTom Flow API for road traffic data."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = BASE_URL,
        http_client: object = None,
        timeout: int = 10,
    ) -> None:
        """Initialize the service."""
        self.api_key = api_key or os.getenv("TOMTOM_API_KEY")
        self.base_url = base_url
        self.http_client = http_client or requests
        self.timeout = timeout

    def get_flow(self, lat: float, lon: float):
        """Query TomTom Flow API for a point and return summarized flow info."""
        params = {
            "key": self.api_key,
            "point": f"{lat},{lon}",
        }

        try:
            response = self.http_client.get(
                self.base_url,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            if "flowSegmentData" not in data:
                return None

            flow = data["flowSegmentData"]
            return {
                "api_version": flow["@version"],
                "speed": flow["currentSpeed"],
                "free_speed": flow["freeFlowSpeed"],
                "travel_time": flow["currentTravelTime"],
                "free_flow_travel_time": flow["freeFlowTravelTime"],
                "confidence": flow["confidence"],
                "road_closed": flow["roadClosure"],
                "frc": flow["frc"],
                "coordinates": flow["coordinates"],
            }
        except Exception:
            return None


_DEFAULT_SERVICE = TomTomFlowService()


def get_flow(lat: float, lon: float):
    """Query TomTom Flow API for a point and return summarized flow info."""
    return _DEFAULT_SERVICE.get_flow(lat, lon)
