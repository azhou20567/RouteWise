"""
Route geometry validators.

Two strictness levels:

  * `validate_polyline_gaps` — pure-Python; asserts no segment in the
    decoded path is longer than `max_segment_km`. Catches straight-line
    connectors between unrelated road shapes. No external API calls.
    (The KC Metro build script uses the equivalent check inline.)

  * `validate_polyline_on_road` — uses Google's Roads API to confirm
    that ≥99% of sampled points along the polyline sit within
    `tolerance_m` of a real road segment. Catches polylines that cut
    across parking lots, water, or private land. One network call per
    100-point batch.

The Roads-API validator is the "checks that bus routes only follow
actual roads" deliverable from the plan. It is exposed via the MCP
server as `validate_route_geometry` so an LLM can re-check a route
without running the full dataset build.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.services.google_maps_service import GoogleMapsService, LatLng

EARTH_RADIUS_M = 6_371_008.8


class RouteValidationError(ValueError):
    """Raised when a polyline fails a geometry check."""


@dataclass
class GapCheckResult:
    longest_segment_m: float
    offending_index: int | None
    threshold_m: float

    @property
    def valid(self) -> bool:
        return self.offending_index is None


@dataclass
class OnRoadCheckResult:
    sampled_points: int
    on_road_points: int
    offending_points: list[LatLng]
    tolerance_m: float
    pass_threshold: float

    @property
    def pass_rate(self) -> float:
        return self.on_road_points / self.sampled_points if self.sampled_points else 1.0

    @property
    def valid(self) -> bool:
        return self.pass_rate >= self.pass_threshold


# ---------------------------------------------------------------------------
# Pure-Python: distance helpers
# ---------------------------------------------------------------------------

def haversine_m(a: LatLng, b: LatLng) -> float:
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat = lat2 - lat1
    dlng = math.radians(b.lng - a.lng)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def _sample_path(path: list[LatLng], sample_every_m: float) -> list[LatLng]:
    """
    Walk the path and emit a point every `sample_every_m` meters along
    its length. Always includes the first and last point.
    """
    if len(path) < 2:
        return list(path)

    out = [path[0]]
    carry = 0.0
    for i in range(1, len(path)):
        a, b = path[i - 1], path[i]
        seg = haversine_m(a, b)
        if seg == 0:
            continue

        while carry + seg >= sample_every_m:
            # Position along the segment where the next sample lands
            t = (sample_every_m - carry) / seg
            out.append(LatLng(
                lat=a.lat + (b.lat - a.lat) * t,
                lng=a.lng + (b.lng - a.lng) * t,
            ))
            # Advance the segment's "consumed" portion
            a = out[-1]
            seg = haversine_m(a, b)
            carry = 0.0

        carry += seg

    out.append(path[-1])
    return out


# ---------------------------------------------------------------------------
# Public validators
# ---------------------------------------------------------------------------

def validate_polyline_gaps(
    path: list[LatLng],
    max_segment_m: float = 1_000.0,
) -> GapCheckResult:
    """
    Asserts no consecutive segment in `path` is longer than
    `max_segment_m`. A gap usually means we stitched together two
    disconnected geometries with a straight line.
    """
    longest = 0.0
    offending_index = None
    for i in range(1, len(path)):
        d = haversine_m(path[i - 1], path[i])
        if d > longest:
            longest = d
        if d > max_segment_m and offending_index is None:
            offending_index = i
    return GapCheckResult(
        longest_segment_m=longest,
        offending_index=offending_index,
        threshold_m=max_segment_m,
    )


def validate_polyline_on_road(
    path: list[LatLng],
    maps: GoogleMapsService,
    *,
    sample_every_m: float = 50.0,
    tolerance_m: float = 15.0,
    pass_threshold: float = 0.99,
) -> OnRoadCheckResult:
    """
    Sample the decoded polyline every `sample_every_m` meters and check
    each sample's distance to the nearest road via the Roads API. Points
    farther than `tolerance_m` from any road are recorded; the polyline
    is considered valid if at least `pass_threshold` fraction pass.
    """
    samples = _sample_path(path, sample_every_m)
    snapped = maps.nearest_roads_batched(samples)

    offending: list[LatLng] = []
    on_road = 0
    for sample, nearest in zip(samples, snapped):
        if nearest is None:
            offending.append(sample)
            continue
        if haversine_m(sample, nearest) <= tolerance_m:
            on_road += 1
        else:
            offending.append(sample)

    return OnRoadCheckResult(
        sampled_points=len(samples),
        on_road_points=on_road,
        offending_points=offending,
        tolerance_m=tolerance_m,
        pass_threshold=pass_threshold,
    )


def assert_polyline_on_road(
    path: list[LatLng],
    maps: GoogleMapsService,
    *,
    sample_every_m: float = 50.0,
    tolerance_m: float = 15.0,
    pass_threshold: float = 0.99,
    label: str = "polyline",
) -> OnRoadCheckResult:
    """Same as validate_polyline_on_road but raises on failure."""
    result = validate_polyline_on_road(
        path, maps,
        sample_every_m=sample_every_m,
        tolerance_m=tolerance_m,
        pass_threshold=pass_threshold,
    )
    if not result.valid:
        raise RouteValidationError(
            f"{label}: {result.on_road_points}/{result.sampled_points} samples "
            f"on road (need ≥ {pass_threshold:.0%}); "
            f"{len(result.offending_points)} offending points."
        )
    return result
