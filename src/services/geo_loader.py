from pathlib import Path

import geopandas as gpd

DATA = Path(__file__).parent.parent/"data"/"wards_lucknow.geojson"

wards = gpd.read_file(DATA)


def get_polygon(ward_no: int):

    ward = wards[wards["Ward Num"] == ward_no]

    if ward.empty:
        raise ValueError("Ward not found")

    return ward.geometry.iloc[0]
