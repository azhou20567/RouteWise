from pydantic import BaseModel
from typing import Optional


class RouteStop(BaseModel):
    stop_id: str
    sequence: int
    arrival_offset_minutes: float


class Route(BaseModel):
    route_id: str
    name: str
    color: str
    bus_capacity: int
    departure_time: str          # "07:52"
    stops: list[RouteStop]
    total_distance_km: float
    total_duration_minutes: float
    avg_load_factor: float
    merged_from: Optional[list[str]] = None


class Stop(BaseModel):
    stop_id: str
    name: str
    lat: float
    lng: float
    zone_id: str
    estimated_riders: int


class Zone(BaseModel):
    zone_id: str
    name: str
    polygon: list[list[float]]   # [[lat, lng], ...]
    school_level: str
    peak_demand_multiplier: float


class OptimizedScenario(BaseModel):
    routes: list[Route]
    eliminated_routes: list[str]
    total_distance_km: float
    total_duration_minutes: float


class TrafficZoneContext(BaseModel):
    congestion_level: str        # "low" | "medium" | "high"
    peak_delay_minutes: float


class TrafficContext(BaseModel):
    peak_window: str
    zones: dict[str, TrafficZoneContext]
    notes: str


class DemandZoneContext(BaseModel):
    estimated_students: int
    current_capacity: int


class DemandContext(BaseModel):
    total_enrolled: int
    bus_eligible_pct: float
    total_estimated_riders: int
    zones: dict[str, DemandZoneContext]
    notes: str


class Dataset(BaseModel):
    dataset_id: str
    name: str
    school_name: str
    school_level: str            # "elementary" | "middle"
    school_lat: float
    school_lng: float
    stops: list[Stop]
    zones: list[Zone]
    routes: list[Route]
    optimized_scenario: OptimizedScenario
    traffic_context: TrafficContext
    demand_context: DemandContext

    def stop_map(self) -> dict[str, Stop]:
        return {s.stop_id: s for s in self.stops}
