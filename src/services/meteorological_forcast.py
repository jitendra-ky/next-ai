"""
Meteorological Evidence Module — AQI Early Warning Agent (prototype)
=====================================================================

Fetches forecast data from Open-Meteo (free, no API key) for a given
location, derives pollution-dispersion signals from it, and outputs a
structured "evidence" block in the same shape used by the agent's
Evidence Collected table (source -> evidence string) plus a machine
readable JSON summary the LLM reasoning step can consume as a tool result.

Usage:
    python met_evidence_agent.py --lat 28.6139 --lon 77.2090 --name "Ward 17, Delhi"

Requires: requests  (pip install requests)
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import requests

# Default data directory relative to this file
DATA_DIR = Path(__file__).parent.parent / "data"

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# Ventilation Coefficient (wind_speed[m/s] * PBL_height[m]) thresholds.
# Below ~3000: very poor dispersion. Above ~6000: good dispersion.
VC_HIGH_RISK_THRESHOLD = 3000
VC_MEDIUM_RISK_THRESHOLD = 6000


def fetch_weather(lat: float, lon: float, forecast_days: int = 3) -> dict:
    """Pull hourly wind, PBL height, humidity, temp, precipitation forecast."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "wind_speed_10m",
            "wind_direction_10m",
            "boundary_layer_height",
            "precipitation",
        ]),
        "forecast_days": forecast_days,
        "timezone": "Asia/Kolkata",
    }
    resp = requests.get(WEATHER_URL, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_air_quality(lat: float, lon: float, forecast_days: int = 3) -> dict:
    """Pull CAMS-based hourly PM2.5/PM10/NO2/O3 forecast (regional background check)."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "pm2_5,pm10,nitrogen_dioxide,ozone",
        "forecast_days": forecast_days,
        "timezone": "Asia/Kolkata",
    }
    resp = requests.get(AIR_QUALITY_URL, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def ventilation_coefficient(wind_speed_kmh: float, pbl_height_m: float) -> float:
    """VC = wind speed (m/s) * boundary layer height (m). Higher = better dispersion."""
    wind_ms = wind_speed_kmh / 3.6
    return round(wind_ms * pbl_height_m, 1)


def dispersion_risk(vc: float) -> str:
    if vc < VC_HIGH_RISK_THRESHOLD:
        return "HIGH"
    if vc < VC_MEDIUM_RISK_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def detect_inversion_risk(hour_index: int, times: list, wind_speed: list, humidity: list) -> bool:
    """
    Simple proxy for a surface temperature inversion, since Open-Meteo's free
    tier does not expose a direct 'inversion' flag. Inversions are most likely
    when: it's early morning (00:00-08:00), wind is calm (<6 km/h), and
    humidity is high (>70%) -- classic radiative cooling conditions.
    """
    hour_str = times[hour_index][11:13]
    hour = int(hour_str)
    is_early_morning = 0 <= hour <= 8
    is_calm = wind_speed[hour_index] < 6
    is_humid = humidity[hour_index] > 70
    return is_early_morning and is_calm and is_humid


def build_hourly_records(weather_json: dict) -> list:
    h = weather_json["hourly"]
    records = []
    for i, t in enumerate(h["time"]):
        wind = h["wind_speed_10m"][i]
        pbl = h["boundary_layer_height"][i]
        vc = ventilation_coefficient(wind, pbl)
        records.append({
            "time": t,
            "temperature_c": h["temperature_2m"][i],
            "humidity_pct": h["relative_humidity_2m"][i],
            "wind_speed_kmh": wind,
            "wind_direction_deg": h["wind_direction_10m"][i],
            "pbl_height_m": pbl,
            "precipitation_mm": h["precipitation"][i],
            "ventilation_coefficient": vc,
            "dispersion_risk": dispersion_risk(vc),
            "inversion_risk": detect_inversion_risk(i, h["time"], h["wind_speed_10m"], h["relative_humidity_2m"]),
        })
    return records


def find_worst_window(records: list, window_hours: int = 3, lookahead_hours: int = 48) -> dict:
    """Find the window (default 3h) in the next N hours with the lowest average VC."""
    candidates = records[:lookahead_hours]
    best = None
    for i in range(len(candidates) - window_hours + 1):
        window = candidates[i:i + window_hours]
        avg_vc = sum(r["ventilation_coefficient"] for r in window) / window_hours
        if best is None or avg_vc < best["avg_ventilation_coefficient"]:
            best = {
                "start_time": window[0]["time"],
                "end_time": window[-1]["time"],
                "avg_ventilation_coefficient": round(avg_vc, 1),
                "avg_wind_kmh": round(sum(r["wind_speed_kmh"] for r in window) / window_hours, 1),
                "avg_pbl_height_m": round(sum(r["pbl_height_m"] for r in window) / window_hours, 1),
                "inversion_expected": any(r["inversion_risk"] for r in window),
                "dispersion_risk": dispersion_risk(avg_vc),
            }
    return best


def build_evidence_summary(name: str, lat: float, lon: float, save_raw: bool = True, data_dir: Path = None) -> dict:
    weather = fetch_weather(lat, lon)
    aq = fetch_air_quality(lat, lon)

    # Save raw fetched data to data folder
    if save_raw:
        save_dir = data_dir or DATA_DIR
        save_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        weather_file = save_dir / f"weather_{timestamp}.json"
        with open(weather_file, "w") as f:
            json.dump(weather, f, indent=2)
        
        aq_file = save_dir / f"air_quality_{timestamp}.json"
        with open(aq_file, "w") as f:
            json.dump(aq, f, indent=2)

    records = build_hourly_records(weather)
    current = records[0]
    worst_window = find_worst_window(records)

    aq_hourly = aq["hourly"]
    current_pm25 = aq_hourly["pm2_5"][0]

    evidence_row = (
        f"Wind expected to drop to {worst_window['avg_wind_kmh']} km/h and boundary layer height "
        f"to ~{worst_window['avg_pbl_height_m']:.0f} m between {worst_window['start_time']} and "
        f"{worst_window['end_time']}, giving a dispersion risk of {worst_window['dispersion_risk']}"
        + (" with a temperature inversion likely." if worst_window["inversion_expected"] else ".")
    )

    return {
        "location": {"name": name, "latitude": lat, "longitude": lon},
        "generated_at": datetime.now().isoformat(timespec="minutes"),
        "current_conditions": current,
        "predicted_worst_dispersion_window": worst_window,
        "cams_background_pm2_5_ugm3": current_pm25,
        "evidence_table_row": {
            "source": "Meteorological Forecast",
            "evidence": evidence_row,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch meteorological evidence for the AQI agent.")
    parser.add_argument("--lat", type=float, required=True, help="Latitude")
    parser.add_argument("--lon", type=float, required=True, help="Longitude")
    parser.add_argument("--name", type=str, default="Location", help="Human-readable location name")
    parser.add_argument("--out", type=str, default="met_evidence.json", help="Output JSON path")
    parser.add_argument("--no-save-raw", action="store_true", help="Disable saving raw fetched data")
    parser.add_argument("--data-dir", type=str, default=None, help="Custom data directory for raw files")
    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else None
    summary = build_evidence_summary(args.name, args.lat, args.lon, 
                                     save_raw=not args.no_save_raw, 
                                     data_dir=data_dir)

    with open(args.out, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n=== Meteorological Evidence: {args.name} ===")
    print(f"Current: wind {summary['current_conditions']['wind_speed_kmh']} km/h, "
          f"PBL {summary['current_conditions']['pbl_height_m']} m, "
          f"VC {summary['current_conditions']['ventilation_coefficient']}, "
          f"risk {summary['current_conditions']['dispersion_risk']}")
    print(f"\nWorst dispersion window (next 48h): "
          f"{summary['predicted_worst_dispersion_window']['start_time']} -> "
          f"{summary['predicted_worst_dispersion_window']['end_time']}")
    print(f"  Avg wind: {summary['predicted_worst_dispersion_window']['avg_wind_kmh']} km/h")
    print(f"  Avg PBL height: {summary['predicted_worst_dispersion_window']['avg_pbl_height_m']} m")
    print(f"  Dispersion risk: {summary['predicted_worst_dispersion_window']['dispersion_risk']}")
    print(f"  Inversion expected: {summary['predicted_worst_dispersion_window']['inversion_expected']}")
    print(f"\nEvidence row for report:\n  {summary['evidence_table_row']['evidence']}")
    print(f"\nFull JSON saved to: {args.out}")


if __name__ == "__main__":
    main()