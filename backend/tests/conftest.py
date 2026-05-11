"""
Shared fixtures for backend tests. Builds a minimal in-memory Dataset so
projection and recommender tests don't depend on the bundled JSON files
or on get_dataset() caching.
"""

import sys
from pathlib import Path

# Make `app` importable when pytest is invoked from the backend/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.models.dataset import (
    Dataset,
    DemandContext,
    DemandZoneContext,
    OptimizedScenario,
    Route,
    RouteStop,
    Stop,
    TrafficContext,
    TrafficZoneContext,
    Zone,
)


@pytest.fixture
def small_dataset() -> Dataset:
    """
    Three stops, two routes (R1 healthy-ish, R2 deeply underutilized),
    one merged optimized route, two zones. Designed so the heuristic
    recommender's underutilization rule fires on R2 (load factor 0.07)
    but not on R1 (load factor 0.25 — still below threshold, also flagged).
    """
    return Dataset(
        dataset_id="test_ds",
        name="Test Dataset",
        school_name="Test Elementary",
        school_level="elementary",
        school_lat=47.6,
        school_lng=-122.2,
        stops=[
            Stop(stop_id="S1", name="Stop 1", lat=47.61, lng=-122.21, zone_id="Z1", estimated_riders=8),
            Stop(stop_id="S2", name="Stop 2", lat=47.62, lng=-122.22, zone_id="Z1", estimated_riders=10),
            Stop(stop_id="S3", name="Stop 3", lat=47.63, lng=-122.23, zone_id="Z2", estimated_riders=5),
        ],
        zones=[
            Zone(
                zone_id="Z1", name="North",
                polygon=[[47.6, -122.2], [47.6, -122.3], [47.7, -122.3], [47.7, -122.2]],
                school_level="elementary", peak_demand_multiplier=1.0,
            ),
            Zone(
                zone_id="Z2", name="South",
                polygon=[[47.5, -122.2], [47.5, -122.3], [47.6, -122.3], [47.6, -122.2]],
                school_level="elementary", peak_demand_multiplier=0.9,
            ),
        ],
        routes=[
            Route(
                route_id="R1", name="Route 1", color="#ff0000", bus_capacity=72,
                departure_time="07:30",
                stops=[
                    RouteStop(stop_id="S2", sequence=2, arrival_offset_minutes=10.0),
                    RouteStop(stop_id="S1", sequence=1, arrival_offset_minutes=5.0),
                ],
                total_distance_km=8.5, total_duration_minutes=22.0, avg_load_factor=0.25,
            ),
            Route(
                route_id="R2", name="Route 2", color="#00ff00", bus_capacity=72,
                departure_time="07:35",
                stops=[
                    RouteStop(stop_id="S3", sequence=1, arrival_offset_minutes=4.0),
                ],
                total_distance_km=5.0, total_duration_minutes=12.0, avg_load_factor=0.07,
            ),
        ],
        optimized_scenario=OptimizedScenario(
            routes=[
                Route(
                    route_id="R1m", name="Route 1 (merged)", color="#ff8800", bus_capacity=72,
                    departure_time="07:30",
                    stops=[
                        RouteStop(stop_id="S1", sequence=1, arrival_offset_minutes=5.0),
                        RouteStop(stop_id="S2", sequence=2, arrival_offset_minutes=10.0),
                        RouteStop(stop_id="S3", sequence=3, arrival_offset_minutes=15.0),
                    ],
                    total_distance_km=11.0, total_duration_minutes=26.0, avg_load_factor=0.32,
                    merged_from=["R1", "R2"],
                ),
            ],
            eliminated_routes=["R2"],
            total_distance_km=11.0,
            total_duration_minutes=26.0,
        ),
        traffic_context=TrafficContext(
            peak_window="07:00-09:00",
            zones={
                "Z1": TrafficZoneContext(congestion_level="medium", peak_delay_minutes=4.0),
                "Z2": TrafficZoneContext(congestion_level="low", peak_delay_minutes=2.0),
            },
            notes="test traffic notes",
        ),
        demand_context=DemandContext(
            total_enrolled=200, bus_eligible_pct=0.7, total_estimated_riders=140,
            zones={
                "Z1": DemandZoneContext(estimated_students=80, current_capacity=72),
                "Z2": DemandZoneContext(estimated_students=60, current_capacity=72),
            },
            notes="test demand notes",
        ),
    )
