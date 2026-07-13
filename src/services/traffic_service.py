from src.services.geo_loader import get_polygon
from src.services.osm_service import get_major_roads
from src.services.tomtom_service import get_flow


def get_traffic_data(ward_no: int):

    polygon = get_polygon(ward_no)

    roads = get_major_roads(polygon)

    speed = []
    free_speed = []
    confidence = []
    road_closed = []

    for row in roads.itertuples():

        flow = get_flow(row.lat, row.lon)

        if flow is None:

            speed.append(None)
            free_speed.append(None)
            confidence.append(None)
            road_closed.append(None)

            continue

        speed.append(flow["speed"])
        free_speed.append(flow["free_speed"])
        confidence.append(flow["confidence"])
        road_closed.append(flow["road_closed"])

    roads["speed"] = speed
    roads["free_speed"] = free_speed
    roads["confidence"] = confidence
    roads["road_closed"] = road_closed

    roads = roads.dropna()

    roads["congestion"] = (
        1- roads["speed"]/roads["free_speed"]) *100

    avg_speed = (roads["speed"] * roads["length"]).sum() /roads["length"].sum()

    avg_congestion = (roads["congestion"] * roads["length"]).sum() / roads["length"].sum()

    return {

        "ward": ward_no,
        "average_speed": round(avg_speed, 2),
        "average_congestion": round(avg_congestion, 2),

        "roads": len(roads),
        "closed_roads": int(roads["road_closed"].fillna(value=False).sum()),
        "confidence": round(roads["confidence"].mean(),2),

    }
