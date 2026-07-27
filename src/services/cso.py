"""Domain models for Common Source Objects (CSO)."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Location:
    """Geospatial coordinates of a pollutant source."""

    lat: float
    lon: float
    geometry_type: str = "point"


@dataclass(frozen=True)
class Activity:
    """Activity metric and value driving emission estimates."""

    metric: str
    value: float | int
    unit: str


@dataclass(frozen=True)
class EmissionRate:
    """Estimated emission rate for a specific pollutant."""

    rate_gs: float
    method: str
    factor_source: str
    confidence: str


@dataclass(frozen=True)
class Provenance:
    """Metadata about data origin and retrieval time."""

    data_source: str
    retrieved_at: str


@dataclass(frozen=True)
class TemporalValidity:
    """Time window and notes regarding the validity of the detection."""

    valid_from: str | None
    valid_until: str | None
    note: str


@dataclass(frozen=True)
class CommonSourceObject:
    """Standardized immutable representation of a pollutant source (CSO).

    All specific source services (e.g., Construction, Fire, Traffic) convert their
    local source representations into this unified dataclass so downstream engines
    can reason over them consistently.
    """

    source_id: str
    source_type: str
    source_subtype: str
    location: Location
    effective_release_height_m: float | int
    activity: Activity
    emission_profile: dict[str, EmissionRate]
    detection_confidence: str
    provenance: Provenance
    temporal_validity: TemporalValidity
    raw_tags: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert the CSO to a plain dictionary for JSON serialization or API responses."""
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "source_subtype": self.source_subtype,
            "location": {
                "lat": self.location.lat,
                "lon": self.location.lon,
                "geometry_type": self.location.geometry_type,
            },
            "effective_release_height_m": self.effective_release_height_m,
            "activity": {
                "metric": self.activity.metric,
                "value": self.activity.value,
                "unit": self.activity.unit,
            },
            "emission_profile": {
                pollutant: {
                    "rate_gs": rate.rate_gs,
                    "method": rate.method,
                    "factor_source": rate.factor_source,
                    "confidence": rate.confidence,
                }
                for pollutant, rate in self.emission_profile.items()
            },
            "detection_confidence": self.detection_confidence,
            "provenance": {
                "data_source": self.provenance.data_source,
                "retrieved_at": self.provenance.retrieved_at,
            },
            "temporal_validity": {
                "valid_from": self.temporal_validity.valid_from,
                "valid_until": self.temporal_validity.valid_until,
                "note": self.temporal_validity.note,
            },
            "raw_tags": self.raw_tags,
        }


# Type alias for convenience
CSO = CommonSourceObject
