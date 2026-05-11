"""
Build a RouteWise dataset for a Bellevue School District school from a
hand-curated candidate-stops YAML.

Input:
  backend/scripts/stops/<school_slug>.yml   (committed; see stops/README.md)

Output:
  backend/app/data/datasets/<dataset_id>.json   (matches the runtime
                                                 Dataset Pydantic shape)

Pipeline (lock decisions from the grilled plan):
  Q2(a) — real BSD + ACS data sourced by the candidate-stops YAML
  Q3(c) — rich YAML schema with provenance per stop
  Q4(b) — ACS × zone peak_demand_multiplier ridership
  Q5(d) — OR-Tools VRP, lex-min buses then distance

Roughly:
  1. Load YAML
  2. Geocode school if school_lat/lng absent
  3. Snap each candidate stop to nearest road (Roads API)
  4. Compute estimated_riders per stop (ACS × zone weight)
  5. Build distance + duration matrix (Distance Matrix API)
  6. Build "before" baseline:  one route per zone (zone-naive)
  7. Run OR-Tools CVRP for "after" (lex-min buses, then distance)
  8. For every route in both scenarios: snap to road via Directions API
  9. Validate every route polyline via Roads API (≥99% within 15 m of road)
 10. Write JSON

Run from backend/:
  python scripts/build_bsd_dataset.py scripts/stops/clyde_hill_elementary.yml
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.optimization.vrp_solver import (  # noqa: E402
    VrpStop, solve_cvrp, zone_naive_partition,
)
from app.services.google_maps_service import (  # noqa: E402
    DirectionsResult, GoogleMapsService, LatLng,
)
from app.services.route_validator import (  # noqa: E402
    assert_polyline_on_road, validate_polyline_gaps,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("build_bsd")

OUTPUT_DIR = BACKEND_DIR / "app" / "data" / "datasets"

ROUTE_COLORS = [
    "#E63946", "#457B9D", "#2A9D8F", "#F4A261",
    "#9B5DE5", "#FB6F92", "#0077B6", "#6A994E",
]


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------

def load_yaml(path: Path) -> dict[str, Any]:
    import yaml  # lazy import; build-time-only dep

    with path.open("r", encoding="utf-8") as fp:
        return yaml.safe_load(fp)


# ---------------------------------------------------------------------------
# Geocoding + stop snapping
# ---------------------------------------------------------------------------

def resolve_school_location(cfg: dict, maps: GoogleMapsService) -> LatLng:
    if "school_lat" in cfg and "school_lng" in cfg:
        return LatLng(lat=cfg["school_lat"], lng=cfg["school_lng"])
    addr = cfg["school_address"]
    log.info("Geocoding school: %s", addr)
    g = maps.geocode(addr)
    log.info("→ %s, %s (%s)", g.lat, g.lng, g.formatted_address)
    return LatLng(lat=g.lat, lng=g.lng)


def resolve_stop_locations(
    raw_stops: list[dict],
    maps: GoogleMapsService,
) -> list[dict]:
    """
    For each candidate stop: geocode if no lat/lng, snap to nearest road,
    and return a list with `lat`, `lng`, `zone_id`, `name`, `source`,
    `confidence`, `notes`, plus the ACS fields used for ridership.
    """
    resolved = []
    for raw in raw_stops:
        name = raw["name"]
        if "lat" in raw and "lng" in raw:
            point = LatLng(lat=raw["lat"], lng=raw["lng"])
        else:
            g = maps.geocode(name + ", Bellevue, WA")
            point = LatLng(lat=g.lat, lng=g.lng)
            log.info("Geocoded %s → %s, %s", name, point.lat, point.lng)

        snapped = maps.snap_to_nearest_road(point)
        if snapped is not None and (snapped.lat, snapped.lng) != (point.lat, point.lng):
            log.info("Snapped %s by %.0f m onto nearest road", name, _haversine_m(point, snapped))
            point = snapped

        resolved.append({
            **raw,
            "lat": round(point.lat, 6),
            "lng": round(point.lng, 6),
        })
    return resolved


def _haversine_m(a: LatLng, b: LatLng) -> float:
    from app.services.route_validator import haversine_m
    return haversine_m(a, b)


# ---------------------------------------------------------------------------
# Ridership (Q4(b): ACS × zone peak_demand_multiplier)
# ---------------------------------------------------------------------------

def compute_estimated_riders(
    stops: list[dict],
    zone_multipliers: dict[str, float],
    bus_eligible_pct: float,
) -> list[int]:
    # Group stops by ACS tract so we can divide tract child counts
    # evenly across the stops that draw from that tract.
    by_tract: dict[str, list[int]] = defaultdict(list)
    for i, stop in enumerate(stops):
        tract = stop.get("riders_acs_tract", f"_no_tract_{i}")
        by_tract[tract].append(i)

    riders = [0] * len(stops)
    for tract, idxs in by_tract.items():
        # Fallback if no ACS data: 6 children per stop is the
        # demo-realistic anchor from the existing synthetic datasets.
        tract_children = stops[idxs[0]].get("riders_tract_children", 6 * len(idxs))
        per_stop_base = (tract_children * bus_eligible_pct) / max(1, len(idxs))
        for i in idxs:
            zone_w = zone_multipliers.get(stops[i]["zone_id"], 1.0)
            riders[i] = max(1, round(per_stop_base * zone_w))
    return riders


# ---------------------------------------------------------------------------
# Build the matrices + run the VRP solver
# ---------------------------------------------------------------------------

def build_matrices(
    school: LatLng,
    stops: list[dict],
    maps: GoogleMapsService,
    departure_unix: int,
) -> tuple[list[list[float]], list[list[float]]]:
    """
    Build (n+1)×(n+1) distance/duration matrices with school as node 0.
    Distance Matrix API allows 25 origins × 25 destinations per call, so
    we chunk if needed.
    """
    points = [school] + [LatLng(lat=s["lat"], lng=s["lng"]) for s in stops]
    n = len(points)

    dist = [[0.0] * n for _ in range(n)]
    dur = [[0.0] * n for _ in range(n)]

    chunk = 10  # 10x10 = 100 elements per call, well under the 100 limit
    for i0 in range(0, n, chunk):
        for j0 in range(0, n, chunk):
            origins = points[i0:i0 + chunk]
            dests = points[j0:j0 + chunk]
            matrix = maps.distance_matrix(origins, dests, departure_time=departure_unix)
            for ii, row in enumerate(matrix):
                for jj, (d, t) in enumerate(row):
                    dist[i0 + ii][j0 + jj] = d
                    dur[i0 + ii][j0 + jj] = t
    return dist, dur


# ---------------------------------------------------------------------------
# Build a Route record (matches Pydantic Route shape)
# ---------------------------------------------------------------------------

def snap_route_polyline(
    school: LatLng,
    ordered_stops: list[dict],
    maps: GoogleMapsService,
    departure_unix: int,
) -> DirectionsResult:
    waypoints = [LatLng(lat=s["lat"], lng=s["lng"]) for s in ordered_stops]
    return maps.directions(
        origin=school,
        destination=school,
        waypoints=waypoints,
        departure_time=departure_unix,
        optimize_waypoints=False,
    )


def make_route_record(
    route_id: str,
    name: str,
    color: str,
    bus_capacity: int,
    departure_time_str: str,
    ordered_stops: list[dict],
    school: LatLng,
    maps: GoogleMapsService,
    departure_unix: int,
    *,
    merged_from: list[str] | None = None,
) -> dict:
    if not ordered_stops:
        raise ValueError(f"Route {route_id} has no stops")

    dr = snap_route_polyline(school, ordered_stops, maps, departure_unix)

    # Validate before persisting
    gap = validate_polyline_gaps([LatLng(lat=p.lat, lng=p.lng) for p in dr.path], max_segment_m=2_000.0)
    if not gap.valid:
        raise ValueError(
            f"Route {route_id} has a {gap.longest_segment_m:.0f} m gap at index "
            f"{gap.offending_index} — Directions API returned a discontinuity?"
        )
    assert_polyline_on_road(
        dr.path, maps,
        sample_every_m=50.0,
        tolerance_m=15.0,
        pass_threshold=0.99,
        label=route_id,
    )

    # Compute per-stop arrival offsets from cumulative leg durations
    arrival_offsets = []
    cumulative_s = 0.0
    # NOTE: directions returns one leg per (origin → wp_1 → wp_2 → … → dest).
    # We want the offset at each waypoint (= each ordered stop except the
    # final school-destination leg). dr.path is the full decoded polyline
    # so we use the high-level leg durations from the raw response. Since
    # we collapsed durations in GoogleMapsService, fall back to evenly
    # distributing the total duration across stops.
    if len(ordered_stops) > 0:
        per_stop_s = dr.duration_s / len(ordered_stops)
        for i in range(len(ordered_stops)):
            cumulative_s += per_stop_s
            arrival_offsets.append(round(cumulative_s / 60.0, 1))

    route_stops = [
        {
            "stop_id": stop["stop_id"],
            "sequence": i + 1,
            "arrival_offset_minutes": arrival_offsets[i],
        }
        for i, stop in enumerate(ordered_stops)
    ]

    riders = sum(s["estimated_riders"] for s in ordered_stops)
    duration_min = (dr.duration_in_traffic_s or dr.duration_s) / 60.0

    return {
        "route_id": route_id,
        "name": name,
        "color": color,
        "bus_capacity": bus_capacity,
        "departure_time": departure_time_str,
        "stops": route_stops,
        "total_distance_km": round(dr.distance_m / 1_000.0, 2),
        "total_duration_minutes": round(duration_min, 1),
        "avg_load_factor": round(riders / bus_capacity, 3),
        "merged_from": merged_from,
        "path": [{"lat": round(p.lat, 6), "lng": round(p.lng, 6)} for p in dr.path],
    }


# ---------------------------------------------------------------------------
# Departure-time helper
# ---------------------------------------------------------------------------

def next_weekday_morning_unix(hour: int = 7, minute: int = 45) -> int:
    """
    Pick a fixed near-future Tuesday morning for traffic_model timing.
    Using a relative-near future minimizes Directions API quirks where
    departure_time can't be in the past.
    """
    now = int(time.time())
    # 7 days out at the given local-ish hour. Bellevue is UTC-8/7; using
    # UTC is fine since we just need a stable timestamp.
    return now + 7 * 86_400 + hour * 3600 + minute * 60


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_dataset(yaml_path: Path) -> dict:
    cfg = load_yaml(yaml_path)
    maps = GoogleMapsService()

    dataset_id = cfg["dataset_id"]
    log.info("Building dataset %s from %s", dataset_id, yaml_path.name)

    school = resolve_school_location(cfg, maps)
    log.info("School: %s (%.6f, %.6f)", cfg["school_name"], school.lat, school.lng)

    # 1. Snap stops to roads
    stops_resolved = resolve_stop_locations(cfg["stops"], maps)
    for i, stop in enumerate(stops_resolved, start=1):
        stop["stop_id"] = f"{cfg.get('stop_id_prefix', 'BSD-S')}{i:02d}"

    # 2. Compute ridership
    zone_multipliers = {z["zone_id"]: z["peak_demand_multiplier"] for z in cfg["zones"]}
    riders = compute_estimated_riders(
        stops_resolved,
        zone_multipliers,
        cfg["demand_context"]["bus_eligible_pct"],
    )
    for stop, r in zip(stops_resolved, riders):
        stop["estimated_riders"] = r

    # 3. Distance/duration matrices
    departure_unix = next_weekday_morning_unix()
    dist, dur = build_matrices(school, stops_resolved, maps, departure_unix)

    # 4. "Before" baseline = zone-naive partition, one route per zone
    zone_for_stop = {s["stop_id"]: s["zone_id"] for s in stops_resolved}
    vrp_stops = [
        VrpStop(stop_id=s["stop_id"], location=LatLng(lat=s["lat"], lng=s["lng"]), riders=s["estimated_riders"])
        for s in stops_resolved
    ]
    before_solutions = zone_naive_partition(vrp_stops, zone_for_stop)
    log.info("Before (zone-naive): %d routes", len(before_solutions))

    # 5. "After" = OR-Tools CVRP, lex-min buses then distance
    after_result = solve_cvrp(
        school=school,
        stops=vrp_stops,
        distance_matrix_m=dist,
        duration_matrix_s=dur,
        max_vehicles=cfg["max_vehicles"],
        bus_capacity=cfg["bus_capacity"],
    )
    log.info(
        "After (OR-Tools): %d routes (%d unused), objective=%d",
        len(after_result.routes),
        after_result.unused_vehicles,
        after_result.objective_value,
    )

    # 6. Build Route records for both scenarios (Directions + validate)
    by_stop_id = {s["stop_id"]: s for s in stops_resolved}
    bus_cap = cfg["bus_capacity"]

    before_routes = []
    base_minute = _parse_hhmm(cfg["departure_window"].split("-")[0])
    for i, sol in enumerate(before_solutions):
        ordered = [by_stop_id[sid] for sid in sol.stop_ids]
        before_routes.append(make_route_record(
            route_id=f"{cfg.get('route_id_prefix', 'BSD-R')}{i + 1}",
            name=f"{cfg['zones'][i]['name']} Zone Loop",
            color=ROUTE_COLORS[i % len(ROUTE_COLORS)],
            bus_capacity=bus_cap,
            departure_time=_fmt_hhmm(base_minute + i * 7),
            ordered_stops=ordered,
            school=school,
            maps=maps,
            departure_unix=departure_unix,
        ))

    after_routes = []
    for i, sol in enumerate(after_result.routes):
        ordered = [by_stop_id[sid] for sid in sol.stop_ids]
        after_routes.append(make_route_record(
            route_id=f"{cfg.get('route_id_prefix', 'BSD-R')}{i + 1}-OPT",
            name=f"Optimized Route {i + 1}",
            color=ROUTE_COLORS[i % len(ROUTE_COLORS)],
            bus_capacity=bus_cap,
            departure_time=_fmt_hhmm(base_minute + i * 8),
            ordered_stops=ordered,
            school=school,
            maps=maps,
            departure_unix=departure_unix,
        ))

    eliminated_route_ids = [
        before_routes[i]["route_id"]
        for i in range(len(after_routes), len(before_routes))
    ]

    # 7. Demand + traffic context
    zone_riders = defaultdict(int)
    for stop in stops_resolved:
        zone_riders[stop["zone_id"]] += stop["estimated_riders"]
    zone_capacity = defaultdict(int)
    for route in before_routes:
        route_zones = {by_stop_id[rs["stop_id"]]["zone_id"] for rs in route["stops"]}
        for zone_id in route_zones:
            zone_capacity[zone_id] += route["bus_capacity"]

    total_riders = sum(zone_riders.values())

    dataset = {
        "dataset_id": dataset_id,
        "name": cfg.get("name", cfg["school_name"]),
        "school_name": cfg["school_name"],
        "school_level": cfg["school_level"],
        "school_lat": round(school.lat, 6),
        "school_lng": round(school.lng, 6),
        "source_name": cfg.get("source_name"),
        "source_url": cfg.get("source_url"),
        "source_version": cfg.get("source_version"),
        "source_notes": cfg.get("source_notes"),
        "stops": [
            {
                "stop_id": s["stop_id"],
                "name": s["name"],
                "lat": s["lat"],
                "lng": s["lng"],
                "zone_id": s["zone_id"],
                "estimated_riders": s["estimated_riders"],
            }
            for s in stops_resolved
        ],
        "zones": [
            {
                "zone_id": z["zone_id"],
                "name": z["name"],
                "polygon": z["polygon"],
                "school_level": cfg["school_level"],
                "peak_demand_multiplier": z["peak_demand_multiplier"],
            }
            for z in cfg["zones"]
        ],
        "routes": before_routes,
        "optimized_scenario": {
            "routes": after_routes,
            "eliminated_routes": eliminated_route_ids,
            "total_distance_km": round(sum(r["total_distance_km"] for r in after_routes), 2),
            "total_duration_minutes": round(sum(r["total_duration_minutes"] for r in after_routes), 1),
        },
        "traffic_context": {
            "peak_window": cfg.get("peak_window_label", "07:00-09:00"),
            "zones": cfg["traffic_context"]["zones"],
            "notes": cfg["traffic_context"]["notes"],
        },
        "demand_context": {
            "total_enrolled": cfg["demand_context"]["total_enrolled"],
            "bus_eligible_pct": cfg["demand_context"]["bus_eligible_pct"],
            "total_estimated_riders": total_riders,
            "zones": {
                zone_id: {
                    "estimated_students": zone_riders[zone_id],
                    "current_capacity": zone_capacity[zone_id] or cfg["bus_capacity"],
                }
                for zone_id in zone_multipliers
            },
            "notes": cfg["demand_context"]["notes"],
        },
    }
    return dataset


def _parse_hhmm(value: str) -> int:
    h, m = value.split(":")
    return int(h) * 60 + int(m)


def _fmt_hhmm(minute_of_day: int) -> str:
    return f"{(minute_of_day // 60) % 24:02d}:{minute_of_day % 60:02d}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Build a RouteWise dataset from a candidate-stops YAML")
    parser.add_argument("yaml_path", type=Path, help="Path to scripts/stops/<school>.yml")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSON path (defaults to app/data/datasets/<dataset_id>.json)",
    )
    args = parser.parse_args()

    if not args.yaml_path.exists():
        raise SystemExit(f"YAML not found: {args.yaml_path}")

    dataset = build_dataset(args.yaml_path)
    out_path = args.out or (OUTPUT_DIR / f"{dataset['dataset_id']}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(dataset, indent=2) + "\n", encoding="utf-8")

    log.info("Wrote %s", out_path)
    log.info(
        "  Stops: %d  |  Before: %d routes  |  After: %d routes  |  Eliminated: %d",
        len(dataset["stops"]),
        len(dataset["routes"]),
        len(dataset["optimized_scenario"]["routes"]),
        len(dataset["optimized_scenario"]["eliminated_routes"]),
    )


if __name__ == "__main__":
    main()
