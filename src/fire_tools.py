"""Tool wrapper exposing fire detection data to LangChain."""

from langchain_core.tools import tool

from src.services.fire_service import FireDetectionService

_fire_service = FireDetectionService()


@tool
def fire_detection_tool(
    lat: float,
    lon: float,
    radius_km: float = 10.0,
) -> list[dict]:
    """Return active fire/hotspot detections near a location from NASA FIRMS.

    Args:
    ----
        lat: Latitude of the search center.
        lon: Longitude of the search center.
        radius_km: Search radius in kilometres (default 10, max 300).

    Returns:
    -------
        List of fire detection dicts with fire_id, lat, lon, frp_mw,
        confidence_pct, brightness_k, scan, track, daynight, acq_date.

    """
    return _fire_service.get_fires(lat, lon, radius_km)


FIRE_TOOLS = [fire_detection_tool]
