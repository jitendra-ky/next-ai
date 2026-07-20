"""Tool wrapper exposing construction site data to LangChain."""

from langchain_core.tools import tool

from src.services.construction_service import ConstructionService

construction_service = ConstructionService()


@tool
def construction_tool(
    lat: float,
    lon: float,
    radius_km: float = 3,
) -> list[dict]:
    """Return nearby construction sites with confidence levels.

    Args:
        lat: Latitude of the center point.
        lon: Longitude of the center point.
        radius_km: Search radius in kilometers (default 3).

    Returns:
        List of construction site dicts with site_id, lat, lon, confidence, etc.

    """
    return construction_service.get_sites(lat, lon, radius_km)


CONSTRUCTION_TOOLS = [construction_tool]
