"""Build a RouteWise fixture from official King County Metro GTFS data.

Input:
  backend/app/data/raw/king_county_metro_gtfs.zip

Output:
  backend/app/data/datasets/king_county_metro_bellevue.json

The GTFS-derived stops, stop order, stop times, and route geometry are real.
RouteWise-specific rider estimates and the optimized scenario are demo values,
because static GTFS does not publish student ridership or optimization plans.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
import urllib.request
import zipfile
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Iterable


BACKEND_DIR = Path(__file__).resolve().parents[1]
RAW_ZIP = BACKEND_DIR / "app" / "data" / "raw" / "king_county_metro_gtfs.zip"
OUTPUT_JSON = BACKEND_DIR / "app" / "data" / "datasets" / "king_county_metro_bellevue.json"

SOURCE_URL = "https://metro.kingcounty.gov/gtfs/google_transit.zip"
TARGET_ROUTE_SHORT_NAMES = ["223", "226", "240", "245", "271", "550", "B Line"]

BELLEVUE_BOUNDS = {
    "lat_min": 47.565,
    "lat_max": 47.655,
    "lng_min": -122.245,
    "lng_max": -122.105,
}

ROUTE_COLORS = {
    "223": "#8E44AD",
    "226": "#E67E22",
    "240": "#2E86AB",
    "245": "#16A085",
    "271": "#C0392B",
    "550": "#2B376E",
    "B Line": "#9C182F",
}

ZONES = [
    {
        "zone_id": "KCM-Z1",
        "name": "Downtown / West Bellevue",
        "polygon": [
            [47.656, -122.246],
            [47.656, -122.190],
            [47.596, -122.190],
            [47.596, -122.246],
        ],
        "school_level": "high",
        "peak_demand_multiplier": 1.15,
    },
    {
        "zone_id": "KCM-Z2",
        "name": "Crossroads / Overlake",
        "polygon": [
            [47.656, -122.190],
            [47.656, -122.105],
            [47.602, -122.105],
            [47.602, -122.190],
        ],
        "school_level": "high",
        "peak_demand_multiplier": 1.05,
    },
    {
        "zone_id": "KCM-Z3",
        "name": "Eastgate / South Bellevue",
        "polygon": [
            [47.602, -122.190],
            [47.602, -122.105],
            [47.565, -122.105],
            [47.565, -122.190],
        ],
        "school_level": "high",
        "peak_demand_multiplier": 0.95,
    },
    {
        "zone_id": "KCM-Z4",
        "name": "South Bellevue / Factoria",
        "polygon": [
            [47.602, -122.246],
            [47.602, -122.190],
            [47.565, -122.190],
            [47.565, -122.246],
        ],
        "school_level": "high",
        "peak_demand_multiplier": 0.9,
    },
]


def read_csv(zf: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    with zf.open(name) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
        return list(csv.DictReader(text))


def iter_csv(zf: zipfile.ZipFile, name: str) -> Iterable[dict[str, str]]:
    with zf.open(name) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
        yield from csv.DictReader(text)


def parse_time(value: str) -> int:
    hours, minutes, seconds = (int(part) for part in value.split(":"))
    return hours * 60 + minutes + round(seconds / 60)


def format_time(minutes: int) -> str:
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def in_bellevue(lat: float, lng: float) -> bool:
    return (
        BELLEVUE_BOUNDS["lat_min"] <= lat <= BELLEVUE_BOUNDS["lat_max"]
        and BELLEVUE_BOUNDS["lng_min"] <= lng <= BELLEVUE_BOUNDS["lng_max"]
    )


def zone_for(lat: float, lng: float) -> str:
    if lng < -122.190 and lat >= 47.596:
        return "KCM-Z1"
    if lng >= -122.190 and lat >= 47.602:
        return "KCM-Z2"
    if lng >= -122.190:
        return "KCM-Z3"
    return "KCM-Z4"


def stable_rider_estimate(stop_id: str) -> int:
    return 3 + sum(ord(char) for char in stop_id) % 5


def slug_route(short_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", short_name.upper()).strip("-")
    return f"KCM-{slug}"


def downsample(items: list, max_items: int) -> list:
    if len(items) <= max_items:
        return items
    indexes = {
        round(i * (len(items) - 1) / (max_items - 1))
        for i in range(max_items)
    }
    return [items[i] for i in sorted(indexes)]


def haversine_km(a: dict[str, float], b: dict[str, float]) -> float:
    radius_km = 6371.0088
    lat1 = math.radians(a["lat"])
    lat2 = math.radians(b["lat"])
    dlat = lat2 - lat1
    dlng = math.radians(b["lng"] - a["lng"])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * radius_km * math.asin(math.sqrt(h))


def path_distance_km(path: list[dict[str, float]]) -> float:
    return sum(haversine_km(path[i - 1], path[i]) for i in range(1, len(path)))


def max_segment_km(path: list[dict[str, float]]) -> float:
    if len(path) < 2:
        return 0.0
    return max(haversine_km(path[i - 1], path[i]) for i in range(1, len(path)))


def to_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def select_trip(
    route_short_name: str,
    trips: list[dict[str, str]],
    trip_stop_times: dict[str, list[dict[str, str]]],
    stops: dict[str, dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    best: tuple[tuple[int, int, int, int], dict[str, str], list[dict[str, str]]] | None = None

    for trip in trips:
        rows = trip_stop_times.get(trip["trip_id"], [])
        area_rows = []
        for row in rows:
            stop = stops.get(row["stop_id"])
            if not stop:
                continue
            lat = float(stop["stop_lat"])
            lng = float(stop["stop_lon"])
            if in_bellevue(lat, lng):
                area_rows.append(row)

        if len(area_rows) < 4:
            continue

        first_minute = parse_time(area_rows[0]["arrival_time"])
        has_bellevue_tc = any(
            "Bellevue Transit Center" in stops[row["stop_id"]]["stop_name"]
            for row in area_rows
        )
        in_morning_window = 360 <= first_minute <= 600
        target_morning = 7 * 60 + 45
        score = (
            1 if in_morning_window else 0,
            len(area_rows),
            1 if has_bellevue_tc else 0,
            -abs(first_minute - target_morning),
        )

        if best is None or score > best[0]:
            best = (score, trip, area_rows)

    if best is None:
        raise RuntimeError(f"No Bellevue-area trip found for route {route_short_name}")
    return best[1], best[2]


def shape_path(
    shape_id: str,
    first_dist: float | None,
    last_dist: float | None,
    shapes: dict[str, list[dict[str, float]]],
) -> list[dict[str, float]]:
    points = shapes.get(shape_id, [])
    if not points:
        return []

    segment: list[dict[str, float]] = []
    if first_dist is not None and last_dist is not None:
        low, high = sorted((first_dist, last_dist))
        segment = [p for p in points if low <= p["dist"] <= high]

    if len(segment) < 2:
        segment = [p for p in points if in_bellevue(p["lat"], p["lng"])]

    return downsample(
        [{"lat": round(p["lat"], 6), "lng": round(p["lng"], 6)} for p in segment],
        180,
    )


def build_route(
    short_name: str,
    route_row: dict[str, str],
    trip: dict[str, str],
    area_rows: list[dict[str, str]],
    stops: dict[str, dict[str, str]],
    shapes: dict[str, list[dict[str, float]]],
    output_stops: dict[str, dict],
) -> dict:
    sampled_rows = downsample(area_rows, 12)
    first_minute = parse_time(sampled_rows[0]["arrival_time"])
    last_minute = parse_time(sampled_rows[-1]["arrival_time"])
    first_dist = to_float(area_rows[0].get("shape_dist_traveled", ""))
    last_dist = to_float(area_rows[-1].get("shape_dist_traveled", ""))

    route_stops = []
    for sequence, row in enumerate(sampled_rows, start=1):
        source_stop = stops[row["stop_id"]]
        stop_id = f"KCM-{source_stop['stop_id']}"
        lat = float(source_stop["stop_lat"])
        lng = float(source_stop["stop_lon"])
        output_stops.setdefault(
            stop_id,
            {
                "stop_id": stop_id,
                "name": source_stop["stop_name"],
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "zone_id": zone_for(lat, lng),
                "estimated_riders": stable_rider_estimate(source_stop["stop_id"]),
            },
        )
        route_stops.append(
            {
                "stop_id": stop_id,
                "sequence": sequence,
                "arrival_offset_minutes": max(0, parse_time(row["arrival_time"]) - first_minute),
            }
        )

    path = shape_path(trip["shape_id"], first_dist, last_dist, shapes)
    if len(path) < 2:
        path = [
            {"lat": output_stops[row["stop_id"]]["lat"], "lng": output_stops[row["stop_id"]]["lng"]}
            for row in route_stops
        ]

    capacity = 100 if short_name in {"B Line", "550"} else 80
    rider_count = sum(output_stops[row["stop_id"]]["estimated_riders"] for row in route_stops)

    return {
        "route_id": slug_route(short_name),
        "name": f"Route {short_name}: {route_row['route_desc']}",
        "color": ROUTE_COLORS[short_name],
        "bus_capacity": capacity,
        "departure_time": format_time(first_minute),
        "stops": route_stops,
        "total_distance_km": round(path_distance_km(path), 2),
        "total_duration_minutes": max(1, last_minute - first_minute),
        "avg_load_factor": round(rider_count / capacity, 3),
        "merged_from": None,
        "path": path,
    }


def resequence(route_stops: list[dict], step_minutes: int = 4) -> list[dict]:
    return [
        {
            "stop_id": row["stop_id"],
            "sequence": index,
            "arrival_offset_minutes": (index - 1) * step_minutes,
        }
        for index, row in enumerate(route_stops, start=1)
    ]


def reversed_stops(route: dict) -> list[dict]:
    return list(reversed(route["stops"]))


def joined_road_path(paths: list[list[dict[str, float]]], max_points: int = 320) -> list[dict[str, float]]:
    joined: list[dict[str, float]] = []
    for path in paths:
        for point in path:
            if joined and point == joined[-1]:
                continue
            joined.append(point)
    return downsample(joined, max_points)


def riders_for_route(route: dict, stops: dict[str, dict]) -> int:
    return sum(stops[row["stop_id"]]["estimated_riders"] for row in route["stops"])


def build_optimized_routes(routes: list[dict], stops: dict[str, dict]) -> tuple[list[dict], list[str]]:
    by_id = {route["route_id"]: route for route in routes}
    eliminated: list[str] = []
    optimized: list[dict] = []

    merge_base = by_id.get("KCM-226")
    merge_extra = by_id.get("KCM-B-LINE")
    if merge_base and merge_extra:
        merged_stops = merge_base["stops"] + reversed_stops(merge_extra)
        merged_path = joined_road_path(
            [
                merge_base.get("path") or [],
                list(reversed(merge_extra.get("path") or [])),
            ]
        )
        merged_distance = round((merge_base["total_distance_km"] + merge_extra["total_distance_km"]) * 0.74, 2)
        capacity = 160
        rider_count = sum(stops[row["stop_id"]]["estimated_riders"] for row in merged_stops)
        optimized.append(
            {
                "route_id": "KCM-226-B-LINE-OPT",
                "name": "Routes 226/B Line Bellevue Through-Run",
                "color": merge_base["color"],
                "bus_capacity": capacity,
                "departure_time": merge_base["departure_time"],
                "stops": resequence(merged_stops),
                "total_distance_km": merged_distance,
                "total_duration_minutes": max(
                    merge_base["total_duration_minutes"],
                    merge_extra["total_duration_minutes"],
                )
                + 14,
                "avg_load_factor": round(rider_count / capacity, 3),
                "merged_from": [merge_base["route_id"], merge_extra["route_id"]],
                "path": merged_path,
            }
        )
        eliminated.append(merge_extra["route_id"])

    for route in routes:
        if route["route_id"] in {"KCM-226", "KCM-B-LINE"} and merge_base and merge_extra:
            continue
        copy = deepcopy(route)
        copy["route_id"] = f"{copy['route_id']}-OPT"
        copy["total_distance_km"] = round(copy["total_distance_km"] * 0.98, 2)
        copy["total_duration_minutes"] = max(1, round(copy["total_duration_minutes"] * 0.98, 1))
        optimized.append(copy)

    return optimized, eliminated


def validate_optimized_paths(routes: list[dict], threshold_km: float = 1.0) -> None:
    """Catch accidental straight-line connectors between unrelated GTFS shapes."""
    for route in routes:
        path = route.get("path") or []
        if len(path) < 2:
            raise ValueError(f"{route['route_id']} is missing GTFS road geometry")
        longest = max_segment_km(path)
        if longest > threshold_km:
            raise ValueError(
                f"{route['route_id']} has a {longest:.2f} km geometry jump; "
                "optimized routes must be assembled from connected GTFS road shapes"
            )


def main() -> None:
    if not RAW_ZIP.exists():
        RAW_ZIP.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {SOURCE_URL}")
        urllib.request.urlretrieve(SOURCE_URL, RAW_ZIP)

    with zipfile.ZipFile(RAW_ZIP) as zf:
        feed_info = read_csv(zf, "feed_info.txt")[0]
        routes_raw = read_csv(zf, "routes.txt")
        stops_raw = {row["stop_id"]: row for row in read_csv(zf, "stops.txt")}
        calendar_raw = read_csv(zf, "calendar.txt")

        weekday_services = {
            row["service_id"]
            for row in calendar_raw
            if any(row[day] == "1" for day in ["monday", "tuesday", "wednesday", "thursday", "friday"])
        }

        route_by_short = {
            row["route_short_name"]: row
            for row in routes_raw
            if row["route_short_name"] in TARGET_ROUTE_SHORT_NAMES
        }
        route_id_to_short = {row["route_id"]: short for short, row in route_by_short.items()}

        trips_by_short: dict[str, list[dict[str, str]]] = defaultdict(list)
        candidate_trip_ids = set()
        for trip in iter_csv(zf, "trips.txt"):
            short = route_id_to_short.get(trip["route_id"])
            if short and trip["service_id"] in weekday_services:
                trips_by_short[short].append(trip)
                candidate_trip_ids.add(trip["trip_id"])

        trip_stop_times: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in iter_csv(zf, "stop_times.txt"):
            if row["trip_id"] in candidate_trip_ids:
                trip_stop_times[row["trip_id"]].append(row)
        for rows in trip_stop_times.values():
            rows.sort(key=lambda item: int(item["stop_sequence"]))

        selected: dict[str, tuple[dict[str, str], list[dict[str, str]]]] = {}
        for short in TARGET_ROUTE_SHORT_NAMES:
            selected[short] = select_trip(short, trips_by_short[short], trip_stop_times, stops_raw)

        selected_shape_ids = {trip["shape_id"] for trip, _ in selected.values()}
        shapes: dict[str, list[dict[str, float]]] = defaultdict(list)
        for row in iter_csv(zf, "shapes.txt"):
            if row["shape_id"] not in selected_shape_ids:
                continue
            shapes[row["shape_id"]].append(
                {
                    "lat": float(row["shape_pt_lat"]),
                    "lng": float(row["shape_pt_lon"]),
                    "sequence": float(row["shape_pt_sequence"]),
                    "dist": float(row["shape_dist_traveled"]),
                }
            )
        for rows in shapes.values():
            rows.sort(key=lambda item: item["sequence"])

        output_stops: dict[str, dict] = {}
        routes = []
        for short in TARGET_ROUTE_SHORT_NAMES:
            trip, area_rows = selected[short]
            routes.append(
                build_route(
                    short,
                    route_by_short[short],
                    trip,
                    area_rows,
                    stops_raw,
                    shapes,
                    output_stops,
                )
            )

    optimized_routes, eliminated_routes = build_optimized_routes(routes, output_stops)
    validate_optimized_paths(optimized_routes)

    zone_students = defaultdict(int)
    zone_capacity = defaultdict(int)
    for stop in output_stops.values():
        zone_students[stop["zone_id"]] += stop["estimated_riders"]
    for route in routes:
        route_zones = {output_stops[row["stop_id"]]["zone_id"] for row in route["stops"]}
        for zone_id in route_zones:
            zone_capacity[zone_id] += route["bus_capacity"]

    total_riders = sum(riders_for_route(route, output_stops) for route in routes)
    dataset = {
        "dataset_id": "king_county_metro_bellevue",
        "name": "King County Metro Bellevue GTFS Sample",
        "school_name": "Bellevue Transit Center (BSD High/Choice)",
        "school_level": "high",
        "school_lat": 47.615509,
        "school_lng": -122.195358,
        "source_name": "King County Metro GTFS static feed",
        "source_url": SOURCE_URL,
        "source_version": feed_info.get("feed_version", ""),
        "source_notes": (
            "Stops, stop order, stop times, and route shapes are generated from the official "
            "King County Metro GTFS feed. Optimized route geometries are assembled only from "
            "connected GTFS shape segments, so map edits stay road-aligned. Rider estimates "
            "and the optimized scenario are RouteWise demo derivations because static GTFS "
            "does not publish student ridership or route optimization plans."
        ),
        "stops": sorted(output_stops.values(), key=lambda row: row["stop_id"]),
        "zones": ZONES,
        "routes": routes,
        "optimized_scenario": {
            "routes": optimized_routes,
            "eliminated_routes": eliminated_routes,
            "total_distance_km": round(sum(route["total_distance_km"] for route in optimized_routes), 2),
            "total_duration_minutes": round(sum(route["total_duration_minutes"] for route in optimized_routes), 1),
        },
        "traffic_context": {
            "peak_window": "06:30-09:00",
            "zones": {
                "KCM-Z1": {"congestion_level": "high", "peak_delay_minutes": 8.0},
                "KCM-Z2": {"congestion_level": "medium", "peak_delay_minutes": 5.0},
                "KCM-Z3": {"congestion_level": "medium", "peak_delay_minutes": 4.5},
                "KCM-Z4": {"congestion_level": "high", "peak_delay_minutes": 7.0},
            },
            "notes": (
                "Bellevue peak-period context for RouteWise testing. The route geometry and "
                "scheduled times come from GTFS; congestion categories are modeled for demo analysis."
            ),
        },
        "demand_context": {
            "total_enrolled": 0,
            "bus_eligible_pct": 0.0,
            "total_estimated_riders": total_riders,
            "zones": {
                zone["zone_id"]: {
                    "estimated_students": zone_students[zone["zone_id"]],
                    "current_capacity": zone_capacity[zone["zone_id"]],
                }
                for zone in ZONES
            },
            "notes": (
                "GTFS does not include rider counts. Estimated riders are deterministic demo "
                "values assigned to real stops so RouteWise metrics and recommendations can run."
            ),
        },
    }

    OUTPUT_JSON.write_text(json.dumps(dataset, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_JSON}")
    print(f"Routes: {len(routes)} before, {len(optimized_routes)} after")
    print(f"Stops: {len(output_stops)}")


if __name__ == "__main__":
    main()
