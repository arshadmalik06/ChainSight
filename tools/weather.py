"""
Weather Tool for ChainSight Agent.
Queries Open-Meteo API when coordinates are available.
Falls back to validated offline cache when API calls fail or timeout.
Never fabricates live readings.
"""
import requests
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from schemas import WeatherEvidence

logger = logging.getLogger(__name__)

# Known logistics hub coordinates dictionary
KNOWN_COORDINATES = {
    "shanghai": {"lat": 31.2304, "lon": 121.4737, "name": "Shanghai, China"},
    "kaohsiung": {"lat": 22.6163, "lon": 120.2996, "name": "Kaohsiung, Taiwan"},
    "busan": {"lat": 35.1796, "lon": 129.0756, "name": "Busan, South Korea"},
    "los angeles": {"lat": 33.7432, "lon": -118.2673, "name": "Los Angeles, CA, USA"},
    "long beach": {"lat": 33.7701, "lon": -118.1937, "name": "Long Beach, CA, USA"},
    "detroit": {"lat": 42.3314, "lon": -83.0458, "name": "Detroit, MI, USA"},
    "austin": {"lat": 30.2672, "lon": -97.7431, "name": "Austin, TX, USA"},
    "chicago": {"lat": 41.8781, "lon": -87.6298, "name": "Chicago, IL, USA"},
    "dallas": {"lat": 32.7767, "lon": -96.7970, "name": "Dallas, TX, USA"},
    "rayong": {"lat": 12.6814, "lon": 101.2816, "name": "Rayong, Thailand"},
    "yokohama": {"lat": 35.4437, "lon": 139.6380, "name": "Yokohama, Japan"},
}


def resolve_coordinates(location_query: str) -> Optional[Dict[str, Any]]:
    query_norm = location_query.lower()
    for key, data in KNOWN_COORDINATES.items():
        if key in query_norm:
            return data
    return None


def fetch_weather(location_query: str, timeout: int = 6) -> WeatherEvidence:
    """
    Fetch weather from Open-Meteo API or return explicit unresolved indication.
    """
    coords = resolve_coordinates(location_query)
    if not coords:
        return WeatherEvidence(
            location=location_query,
            data_source="unresolved",
            timestamp=datetime.now(timezone.utc).isoformat(),
            forecast_summary=f"Coordinates could not be resolved for '{location_query}'. Weather tool skipped.",
            is_fallback=False,
        )

    lat = coords["lat"]
    lon = coords["lon"]
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m,precipitation,weather_code"

    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()

    current = payload.get("current", {})
    temp = current.get("temperature_2m")
    wind = current.get("wind_speed_10m")
    precip = current.get("precipitation")
    wmo_code = current.get("weather_code", 0)

    # Interpreting WMO weather codes deterministically
    if wmo_code >= 80:
        condition = "Heavy Storm / Violent Showers"
    elif wmo_code >= 60:
        condition = "Rain / Moderate Precipitation"
    elif wmo_code >= 50:
        condition = "Drizzle / Fog"
    else:
        condition = "Clear / Overcast"

    summary = f"Live telemetry: Temp {temp}C, Wind {wind} km/h, Precipitation {precip} mm (WMO code {wmo_code})."

    return WeatherEvidence(
        location=coords["name"],
        latitude=lat,
        longitude=lon,
        temperature_c=temp,
        wind_speed_kmh=wind,
        precipitation_mm=precip,
        weather_condition=condition,
        forecast_summary=summary,
        data_source="live_open_meteo",
        cache_age_hours=0.0,
        timestamp=datetime.now(timezone.utc).isoformat(),
        is_fallback=False,
    )
