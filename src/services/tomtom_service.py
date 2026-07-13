import os

import requests

API_KEY = os.getenv("TOMTOM_API_KEY")

BASE_URL = (
    "https://api.tomtom.com/traffic/services/4/"
    "flowSegmentData/absolute/10/json"
)


def get_flow(lat: float, lon: float):

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
