from pydantic import BaseModel
from typing import Optional


# --- get_route_summary ---

class StopSummary(BaseModel):
    stop_id: str
    name: str
    estimated_riders: int
    zone_id: str
    arrival_offset_minutes: float


class RouteSummary(BaseModel):
    dataset_id: str
    route_id: str
    route_name: str
    color: str
    num_stops: int
    stops: list[StopSummary]
    total_distance_km: float
    total_duration_minutes: float
    bus_capacity: int
    estimated_riders: int
    avg_load_factor: float
    departure_time: str


# --- get_traffic_snapshot ---

class TrafficCondition(BaseModel):
    zone_id: str
    zone_name: str
    congestion_level: str        # "low" | "medium" | "high"
    peak_delay_minutes: float


class TrafficSnapshot(BaseModel):
    dataset_id: str
    snapshot_time: str
    conditions: list[TrafficCondition]
    overall_avg_delay_minutes: float
    notes: str


# --- get_demand_estimate ---

class ZoneDemand(BaseModel):
    zone_id: str
    zone_name: str
    estimated_students: int
    current_capacity: int
    utilization_pct: float
    underserved: bool


class DemandEstimate(BaseModel):
    dataset_id: str
    total_estimated_students: int
    total_bus_capacity: int
    overall_utilization_pct: float
    zone_demand: list[ZoneDemand]
    demand_notes: str
