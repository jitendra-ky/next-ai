"""Dispersion engine to compute pollutant concentration contribution at a target.

Given one Common Source Object (CSO), a target location, and a meteorology snapshot,
it computes per-pollutant concentration contribution at the target.

Design notes (SOLID):
- SRP: geometry math, dispersion-coefficient math, concentration physics, and
  confidence combination are each their own class with one job.
- OCP: each of those is defined behind an abstract interface (ABC), so a new
  dispersion scheme, a geodesic geometry calculator, or a different confidence
  policy can be added without touching DispersionEvaluator or existing classes.
- LSP: any concrete implementation of an interface can replace another without
  breaking DispersionEvaluator's expectations.
- ISP: each interface exposes exactly one method - callers never depend on
  methods they don't use.
- DIP: DispersionEvaluator depends only on the abstract interfaces, supplied via
  constructor injection - not on any concrete implementation.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta

# ----------------------------------------------------------------------
# Plain input/output data structures
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class Target:
    """Represents a target location for dispersion evaluation."""

    lat: float
    lon: float
    receptor_height_m: float = 0.0


@dataclass(frozen=True)
class MeteorologySnapshot:
    """Represents meteorological conditions at a specific time."""

    wind_speed_ms: float
    wind_direction_deg: float  # meteorological convention: direction wind blows FROM
    stability_class: str  # Pasquill-Gifford "A".."F", already classified upstream
    valid_at: datetime
    data_source: str = "unknown"  # "live" | "forecast" | "fallback"


@dataclass(frozen=True)
class GeometryResult:
    """Results of geometry calculations between source and target."""

    distance_km: float
    bearing_source_to_target_deg: float
    downwind_distance_m: float
    crosswind_offset_m: float
    is_upwind: bool


@dataclass(frozen=True)
class TransportResult:
    """Estimated transport time and arrival for pollutants."""

    estimated_travel_time_s: float | None
    estimated_arrival_time: datetime | None


@dataclass(frozen=True)
class PollutantContribution:
    """Contribution of a single pollutant at the target."""

    concentration_ugm3: float
    emission_rate_used_gs: float
    confidence: str


@dataclass(frozen=True)
class DispersionResult:
    """Complete result of a dispersion evaluation."""

    source_id: str
    target: Target
    evaluated_at: datetime
    geometry: GeometryResult
    transport: TransportResult
    meteorology_used: MeteorologySnapshot
    pollutant_contributions: dict  # pollutant name -> PollutantContribution
    overall_confidence: str
    model_metadata: dict

    def to_dict(self) -> dict:
        """Convert the result to a dictionary representation."""
        return {
            "source_id": self.source_id,
            "target": {"lat": self.target.lat, "lon": self.target.lon},
            "evaluated_at": self.evaluated_at.isoformat(),
            "geometry": {
                "distance_km": round(self.geometry.distance_km, 3),
                "bearing_source_to_target_deg": round(
                    self.geometry.bearing_source_to_target_deg, 1
                ),
                "downwind_distance_m": round(self.geometry.downwind_distance_m, 1),
                "crosswind_offset_m": round(self.geometry.crosswind_offset_m, 1),
                "is_upwind": self.geometry.is_upwind,
            },
            "transport": {
                "estimated_travel_time_s": (
                    round(self.transport.estimated_travel_time_s, 1)
                    if self.transport.estimated_travel_time_s is not None
                    else None
                ),
                "estimated_arrival_time": (
                    self.transport.estimated_arrival_time.isoformat()
                    if self.transport.estimated_arrival_time is not None
                    else None
                ),
            },
            "meteorology_used": {
                "wind_speed_ms": self.meteorology_used.wind_speed_ms,
                "wind_direction_deg": self.meteorology_used.wind_direction_deg,
                "stability_class": self.meteorology_used.stability_class,
                "data_source": self.meteorology_used.data_source,
            },
            "pollutant_contributions": {
                p: {
                    "concentration_ugm3": round(c.concentration_ugm3, 6),
                    "emission_rate_used_gs": c.emission_rate_used_gs,
                    "confidence": c.confidence,
                }
                for p, c in self.pollutant_contributions.items()
            },
            "overall_confidence": self.overall_confidence,
            "model_metadata": self.model_metadata,
        }


# ----------------------------------------------------------------------
# Interfaces (abstractions the orchestrator depends on - DIP)
# ----------------------------------------------------------------------


class IGeometryCalculator(ABC):
    """Abstract interface for geometry calculations."""

    @abstractmethod
    def compute(  # noqa: PLR0913
        self,
        source_lat: float,
        source_lon: float,
        target_lat: float,
        target_lon: float,
        wind_direction_deg: float,
    ) -> GeometryResult:
        """Compute the geometry from the source to the target."""
        ...


class IDispersionCoefficientModel(ABC):
    """Abstract interface for dispersion coefficient calculations."""

    @abstractmethod
    def sigma_yz(self, downwind_distance_m: float, stability_class: str) -> tuple[float, float]:
        """Calculate the dispersion coefficients (sigma y and z)."""
        ...


class IConcentrationModel(ABC):
    """Abstract interface for concentration modeling."""

    @abstractmethod
    def compute_concentration(  # noqa: PLR0913
        self,
        downwind_m: float,
        crosswind_m: float,
        receptor_height_m: float,
        source_height_m: float,
        emission_rate_gs: float,
        wind_speed_ms: float,
        stability_class: str,
    ) -> float:
        """Return concentration in g/m^3."""
        ...


class IConfidenceCombiner(ABC):
    """Abstract interface for combining confidence signals."""

    @abstractmethod
    def combine(
        self,
        source_detection_confidence: str,
        pollutant_confidences: list[str],
        meteorology_data_source: str,
    ) -> str:
        """Combine multiple confidence signals into an overall rating."""
        ...


# ----------------------------------------------------------------------
# Concrete implementations
# ----------------------------------------------------------------------


class PlanarGeometryCalculator(IGeometryCalculator):
    """Flat-earth (equirectangular) approximation.

    Accurate enough at ward/city scale (tens of km). Swap for a geodesic
    implementation if sources at 100+ km (e.g. regional fires) need to be
    handled precisely.
    """

    EARTH_M_PER_DEG_LAT = 111_320.0

    def _to_local_m(self, lat0: float, lon0: float, lat: float, lon: float) -> tuple[float, float]:
        north = (lat - lat0) * self.EARTH_M_PER_DEG_LAT
        east = (lon - lon0) * self.EARTH_M_PER_DEG_LAT * math.cos(math.radians(lat0))
        return east, north

    def compute(  # noqa: PLR0913
        self,
        source_lat: float,
        source_lon: float,
        target_lat: float,
        target_lon: float,
        wind_direction_deg: float,
    ) -> GeometryResult:
        """Compute the geometry from the source to the target location."""
        east, north = self._to_local_m(source_lat, source_lon, target_lat, target_lon)
        distance_km = math.hypot(east, north) / 1000.0
        bearing = math.degrees(math.atan2(east, north)) % 360.0

        travel_bearing = (wind_direction_deg + 180.0) % 360.0
        math_angle = math.radians(90.0 - travel_bearing)
        downwind = east * math.cos(math_angle) + north * math.sin(math_angle)
        crosswind = -east * math.sin(math_angle) + north * math.cos(math_angle)

        return GeometryResult(
            distance_km=distance_km,
            bearing_source_to_target_deg=bearing,
            downwind_distance_m=downwind,
            crosswind_offset_m=crosswind,
            is_upwind=downwind > 0,
        )


class BriggsRuralDispersionCoefficients(IDispersionCoefficientModel):
    """Briggs' rural sigma_y / sigma_z parameterization, keyed by Pasquill-Gifford class."""

    _COEFFS = {
        "A": (0.22, 0.20, None),
        "B": (0.16, 0.12, None),
        "C": (0.11, 0.08, 0.0002),
        "D": (0.08, 0.06, 0.0015),
        "E": (0.06, 0.03, 0.0003),
        "F": (0.04, 0.016, 0.0003),
    }

    def sigma_yz(self, downwind_distance_m: float, stability_class: str) -> tuple[float, float]:
        """Calculate the dispersion coefficients (sigma y and z)."""
        x = max(downwind_distance_m, 1e-6)
        ay, az, k = self._COEFFS[stability_class]
        sigma_y = ay * x * (1 + 0.0001 * x) ** -0.5
        if stability_class in ("A", "B"):
            sigma_z = az * x
        elif stability_class in ("C", "D"):
            sigma_z = az * x * (1 + k * x) ** -0.5
        else:
            sigma_z = az * x * (1 + k * x) ** -1
        return sigma_y, sigma_z


class GaussianPlumeConcentrationModel(IConcentrationModel):
    """Steady-state, ground-reflected Gaussian plume.

    Depends on an injected IDispersionCoefficientModel rather than owning
    that math itself (SRP + DIP) - a different stability/coefficient
    scheme can be substituted without changing this class.
    """

    def __init__(self, coefficient_model: IDispersionCoefficientModel) -> None:
        """Initialize the model with a dispersion coefficient calculator."""
        self._coefficients = coefficient_model

    def compute_concentration(  # noqa: PLR0913
        self,
        downwind_m: float,
        crosswind_m: float,
        receptor_height_m: float,
        source_height_m: float,
        emission_rate_gs: float,
        wind_speed_ms: float,
        stability_class: str,
    ) -> float:
        """Compute the pollutant concentration using a Gaussian plume model."""
        if downwind_m <= 0 or emission_rate_gs <= 0:
            return 0.0

        sigma_y, sigma_z = self._coefficients.sigma_yz(downwind_m, stability_class)
        u = max(wind_speed_ms, 0.5)  # avoid divide-by-zero at calm

        term1 = emission_rate_gs / (2 * math.pi * u * sigma_y * sigma_z)
        term2 = math.exp(-(crosswind_m**2) / (2 * sigma_y**2))
        term3 = math.exp(
            -((receptor_height_m - source_height_m) ** 2) / (2 * sigma_z**2)
        ) + math.exp(-((receptor_height_m + source_height_m) ** 2) / (2 * sigma_z**2))
        return term1 * term2 * term3


class WeakestLinkConfidenceCombiner(IConfidenceCombiner):
    """Overall confidence = the weakest of all contributing signals."""

    _ORDER = ["high", "medium", "low"]  # index 0 = strongest
    _METEOROLOGY_CONFIDENCE = {"live": "high", "forecast": "medium", "fallback": "low"}

    def combine(
        self,
        source_detection_confidence: str,
        pollutant_confidences: list[str],
        meteorology_data_source: str,
    ) -> str:
        """Combine multiple confidence signals into an overall confidence rating."""
        signals = [source_detection_confidence, *pollutant_confidences]
        signals.append(self._METEOROLOGY_CONFIDENCE.get(meteorology_data_source, "low"))
        # weakest link = the one furthest down _ORDER; unrecognized values treated as weakest
        return max(
            signals, key=lambda s: self._ORDER.index(s) if s in self._ORDER else len(self._ORDER)
        )


# ----------------------------------------------------------------------
# Orchestrator - depends only on the interfaces above (DIP)
# ----------------------------------------------------------------------


class DispersionEvaluator:
    """Orchestrates the dispersion evaluation process."""

    def __init__(
        self,
        geometry_calculator: IGeometryCalculator,
        concentration_model: IConcentrationModel,
        confidence_combiner: IConfidenceCombiner,
    ) -> None:
        """Initialize the evaluator with its dependencies."""
        self._geometry = geometry_calculator
        self._concentration = concentration_model
        self._confidence = confidence_combiner

    def evaluate(
        self, source: dict, target: Target, meteorology: MeteorologySnapshot
    ) -> DispersionResult:
        """Evaluate the dispersion from a source to a target.

        source: a Common Source Object (dict), as produced by e.g.
        ConstructionCSOConverter.convert().
        Always returns a full result, including sources that turn out not to be
        upwind (geometry.is_upwind = False, all pollutant concentrations = 0) -
        so callers can distinguish "checked, irrelevant" from "not evaluated".
        """
        geometry = self._geometry.compute(
            source["location"]["lat"],
            source["location"]["lon"],
            target.lat,
            target.lon,
            meteorology.wind_direction_deg,
        )

        travel_time_s = None
        arrival_time = None
        if geometry.is_upwind and meteorology.wind_speed_ms > 0:
            travel_time_s = geometry.downwind_distance_m / max(meteorology.wind_speed_ms, 0.5)
            arrival_time = meteorology.valid_at + timedelta(seconds=travel_time_s)

        pollutant_contributions = {}
        for pollutant, profile in source["emission_profile"].items():
            conc_gm3 = self._concentration.compute_concentration(
                downwind_m=geometry.downwind_distance_m,
                crosswind_m=geometry.crosswind_offset_m,
                receptor_height_m=target.receptor_height_m,
                source_height_m=source["effective_release_height_m"],
                emission_rate_gs=profile["rate_gs"],
                wind_speed_ms=meteorology.wind_speed_ms,
                stability_class=meteorology.stability_class,
            )
            pollutant_contributions[pollutant] = PollutantContribution(
                concentration_ugm3=conc_gm3 * 1e6,
                emission_rate_used_gs=profile["rate_gs"],
                confidence=profile.get("confidence", "low"),
            )

        overall_confidence = self._confidence.combine(
            source_detection_confidence=source.get("detection_confidence", "low"),
            pollutant_confidences=[c.confidence for c in pollutant_contributions.values()],
            meteorology_data_source=meteorology.data_source,
        )

        return DispersionResult(
            source_id=source["source_id"],
            target=target,
            evaluated_at=meteorology.valid_at,
            geometry=geometry,
            transport=TransportResult(travel_time_s, arrival_time),
            meteorology_used=meteorology,
            pollutant_contributions=pollutant_contributions,
            overall_confidence=overall_confidence,
            model_metadata={
                "dispersion_model": "gaussian_plume_steady_state",
                "stability_scheme": "pasquill_gifford_briggs_rural",
                "assumptions": [
                    "no plume rise",
                    "no chemical transformation in transit",
                    "steady-state (no puff/time-varying release)",
                ],
            },
        )


def build_default_evaluator() -> DispersionEvaluator:
    """Build a default evaluator using the default concrete implementations."""
    coefficients = BriggsRuralDispersionCoefficients()
    return DispersionEvaluator(
        geometry_calculator=PlanarGeometryCalculator(),
        concentration_model=GaussianPlumeConcentrationModel(coefficients),
        confidence_combiner=WeakestLinkConfidenceCombiner(),
    )
