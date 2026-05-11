"""
Google Maps service wrapper. Used by the BSD dataset build script and the
MCP geocode / validate_route_geometry tools.

Caches every external response to backend/.cache/maps/ keyed by a SHA-256
hash of the request, so re-runs of the build script don't re-bill quota.
Cache invalidation is manual: delete the file (or the whole .cache dir).

This module is NOT imported by the FastAPI runtime — the live API serves
dataset JSONs that have already been baked. Imports of `googlemaps` only
happen here, so a missing optional dep doesn't break the server.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.config import settings

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "maps"


@dataclass(frozen=True)
class LatLng:
    lat: float
    lng: float

    def as_tuple(self) -> tuple[float, float]:
        return (self.lat, self.lng)


@dataclass(frozen=True)
class GeocodeResult:
    lat: float
    lng: float
    formatted_address: str


@dataclass(frozen=True)
class DirectionsResult:
    encoded_polyline: str             # Google-encoded polyline (compact wire form)
    path: list[LatLng]                # Decoded points — what the frontend renders
    distance_m: float
    duration_s: float
    duration_in_traffic_s: float | None
    waypoint_order: list[int]         # If waypoint optimization requested


class GoogleMapsService:
    """
    Thin adapter around the official `googlemaps` Python client plus a
    disk cache. Every public method is a deterministic projection of its
    inputs onto an external API response — no in-memory state.
    """

    def __init__(self, api_key: str | None = None, cache_dir: Path | None = None):
        key = api_key or settings.google_maps_backend_api_key
        if not key:
            raise RuntimeError(
                "GOOGLE_MAPS_BACKEND_API_KEY is not configured. "
                "Set it in .env or pass api_key= explicitly."
            )

        # Lazy import so the FastAPI runtime stays unaffected if the
        # build-time dep isn't installed.
        import googlemaps  # type: ignore[import-not-found]
        import polyline as polyline_codec  # type: ignore[import-not-found]

        self._client = googlemaps.Client(key=key, timeout=20)
        self._decode_polyline = polyline_codec.decode
        self._cache_dir = cache_dir or CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Cache plumbing
    # ------------------------------------------------------------------

    def _cache_path(self, namespace: str, payload: dict) -> Path:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(encoded).hexdigest()[:24]
        return self._cache_dir / f"{namespace}-{digest}.json"

    def _cached(self, namespace: str, payload: dict, fetch):
        path = self._cache_path(namespace, payload)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        logger.info("Maps cache miss: %s", path.name)
        result = fetch()
        path.write_text(json.dumps(result), encoding="utf-8")
        return result

    # ------------------------------------------------------------------
    # Geocoding
    # ------------------------------------------------------------------

    def geocode(self, address: str) -> GeocodeResult:
        raw = self._cached(
            "geocode",
            {"address": address},
            lambda: self._client.geocode(address),
        )
        if not raw:
            raise ValueError(f"Geocoding returned no results for: {address!r}")
        top = raw[0]
        loc = top["geometry"]["location"]
        return GeocodeResult(
            lat=loc["lat"],
            lng=loc["lng"],
            formatted_address=top.get("formatted_address", address),
        )

    # ------------------------------------------------------------------
    # Roads API — snap-to-road and per-point validation
    # ------------------------------------------------------------------

    def snap_to_nearest_road(self, point: LatLng) -> LatLng:
        """
        Move one point onto the nearest paved street. Used during dataset
        build to ensure stops land on real roads rather than the middle of
        a block.
        """
        raw = self._cached(
            "nearest_roads",
            {"points": [point.as_tuple()]},
            lambda: self._client.nearest_roads([point.as_tuple()]),
        )
        if not raw:
            return point
        loc = raw[0]["location"]
        return LatLng(lat=loc["latitude"], lng=loc["longitude"])

    def nearest_roads_batched(self, points: list[LatLng]) -> list[LatLng | None]:
        """
        Snap many points. Returns None for any point with no nearby road.
        Google's nearest_roads accepts 100 points per call; we batch.
        """
        out: list[LatLng | None] = []
        for chunk_start in range(0, len(points), 100):
            chunk = points[chunk_start:chunk_start + 100]
            raw = self._cached(
                "nearest_roads",
                {"points": [p.as_tuple() for p in chunk]},
                lambda: self._client.nearest_roads([p.as_tuple() for p in chunk]),
            )

            # The API returns one entry per snapped point with an
            # originalIndex pointing back into our input list — entries
            # for unsnappable points are simply omitted.
            by_index: dict[int, LatLng] = {}
            for entry in raw:
                idx = entry.get("originalIndex")
                loc = entry.get("location", {})
                if idx is None or "latitude" not in loc:
                    continue
                by_index[int(idx)] = LatLng(lat=loc["latitude"], lng=loc["longitude"])

            for i in range(len(chunk)):
                out.append(by_index.get(i))
        return out

    # ------------------------------------------------------------------
    # Directions — road-snapped polyline + traffic-aware duration
    # ------------------------------------------------------------------

    def directions(
        self,
        origin: LatLng,
        destination: LatLng,
        waypoints: Iterable[LatLng] = (),
        *,
        departure_time: int | None = None,
        traffic_model: str = "best_guess",
        optimize_waypoints: bool = False,
    ) -> DirectionsResult:
        wps = list(waypoints)
        request = {
            "origin": origin.as_tuple(),
            "destination": destination.as_tuple(),
            "waypoints": [p.as_tuple() for p in wps],
            "departure_time": departure_time,
            "traffic_model": traffic_model,
            "optimize_waypoints": optimize_waypoints,
            "mode": "driving",
            "alternatives": False,
        }
        raw = self._cached(
            "directions",
            request,
            lambda: self._client.directions(**{k: v for k, v in request.items() if v is not None}),
        )
        if not raw:
            raise ValueError(
                f"Directions API returned no routes for origin={origin} dest={destination} "
                f"with {len(wps)} waypoints."
            )

        top = raw[0]
        encoded = top["overview_polyline"]["points"]
        decoded_tuples = self._decode_polyline(encoded)
        path = [LatLng(lat=lat, lng=lng) for lat, lng in decoded_tuples]

        distance_m = sum(leg["distance"]["value"] for leg in top["legs"])
        duration_s = sum(leg["duration"]["value"] for leg in top["legs"])
        duration_in_traffic_s = None
        if any("duration_in_traffic" in leg for leg in top["legs"]):
            duration_in_traffic_s = sum(
                leg.get("duration_in_traffic", leg["duration"])["value"]
                for leg in top["legs"]
            )

        return DirectionsResult(
            encoded_polyline=encoded,
            path=path,
            distance_m=float(distance_m),
            duration_s=float(duration_s),
            duration_in_traffic_s=float(duration_in_traffic_s) if duration_in_traffic_s else None,
            waypoint_order=list(top.get("waypoint_order", list(range(len(wps))))),
        )

    # ------------------------------------------------------------------
    # Distance Matrix — feeds the VRP solver
    # ------------------------------------------------------------------

    def distance_matrix(
        self,
        origins: list[LatLng],
        destinations: list[LatLng],
        *,
        departure_time: int | None = None,
    ) -> list[list[tuple[float, float]]]:
        """
        Returns matrix[i][j] = (distance_m, duration_s) for the road
        distance and duration from origins[i] to destinations[j].
        """
        request = {
            "origins": [p.as_tuple() for p in origins],
            "destinations": [p.as_tuple() for p in destinations],
            "departure_time": departure_time,
            "mode": "driving",
        }
        raw = self._cached(
            "distance_matrix",
            request,
            lambda: self._client.distance_matrix(
                **{k: v for k, v in request.items() if v is not None}
            ),
        )
        rows = raw.get("rows", [])
        out: list[list[tuple[float, float]]] = []
        for row in rows:
            row_out: list[tuple[float, float]] = []
            for elem in row.get("elements", []):
                if elem.get("status") != "OK":
                    row_out.append((float("inf"), float("inf")))
                    continue
                dist = float(elem["distance"]["value"])
                dur = float(elem.get("duration_in_traffic", elem["duration"])["value"])
                row_out.append((dist, dur))
            out.append(row_out)
        return out
