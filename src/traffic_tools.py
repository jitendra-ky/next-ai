from langchain_core.tools import tool

from src.services.traffic_service import get_traffic_data


@tool
def traffic_tool(ward_no: int):
    """
    Get real-time traffic information for a ward.

    Args:
        ward_no: Ward number.

    Returns:
        Dictionary containing traffic statistics.
    """

    return get_traffic_data(ward_no)