from pydantic import BaseModel
from typing import Optional

from app.models.tool_outputs import (
    DemandEstimate,
    RouteSummary,
    StopSummary,
    TrafficCondition,
    TrafficSnapshot,
    ZoneDemand,
)


class RouteStop(BaseModel):
    stop_id: str
    sequence: int
    arrival_offset_minutes: float


class RoutePathPoint(BaseModel):
    lat: float
    lng: float


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
    path: Optional[list[RoutePathPoint]] = None


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
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    source_version: Optional[str] = None
    source_notes: Optional[str] = None
    stops: list[Stop]
    zones: list[Zone]
    routes: list[Route]
    optimized_scenario: OptimizedScenario
    traffic_context: TrafficContext
    demand_context: DemandContext

    def stop_map(self) -> dict[str, Stop]:
        return {s.stop_id: s for s in self.stops}

    # ------------------------------------------------------------------
    # Dataset projections — how the Dataset describes itself to the LLM.
    # Each method is a pure function of `self`; no I/O, no config reads.
    # Same shapes are returned to MCP clients, the FastAPI tool endpoints,
    # and the LLM agentic loop, so the projection is the single source
    # of truth for "what the LLM sees about this dataset."
    # ------------------------------------------------------------------

    def route_summary(self, route_id: str) -> RouteSummary:
        route = next((r for r in self.routes if r.route_id == route_id), None)
        if route is None:
            available = [r.route_id for r in self.routes]
            raise ValueError(f"Route '{route_id}' not found. Available: {available}")

        stop_index = self.stop_map()
        stops: list[StopSummary] = []
        for rs in sorted(route.stops, key=lambda x: x.sequence):
            stop = stop_index.get(rs.stop_id)
            if stop is None:
                continue
            stops.append(StopSummary(
                stop_id=stop.stop_id,
                name=stop.name,
                estimated_riders=stop.estimated_riders,
                zone_id=stop.zone_id,
                arrival_offset_minutes=rs.arrival_offset_minutes,
            ))

        riders = sum(s.estimated_riders for s in stops)
        load_factor = riders / route.bus_capacity if route.bus_capacity > 0 else 0.0

        return RouteSummary(
            dataset_id=self.dataset_id,
            route_id=route.route_id,
            route_name=route.name,
            color=route.color,
            num_stops=len(stops),
            stops=stops,
            total_distance_km=route.total_distance_km,
            total_duration_minutes=route.total_duration_minutes,
            bus_capacity=route.bus_capacity,
            estimated_riders=riders,
            avg_load_factor=round(load_factor, 3),
            departure_time=route.departure_time,
        )

    def traffic_snapshot(self) -> TrafficSnapshot:
        tc = self.traffic_context
        zone_index = {z.zone_id: z for z in self.zones}

        conditions = [
            TrafficCondition(
                zone_id=zone_id,
                zone_name=zone_index[zone_id].name if zone_id in zone_index else zone_id,
                congestion_level=zone_tc.congestion_level,
                peak_delay_minutes=zone_tc.peak_delay_minutes,
            )
            for zone_id, zone_tc in tc.zones.items()
        ]

        avg_delay = (
            sum(c.peak_delay_minutes for c in conditions) / len(conditions)
            if conditions else 0.0
        )

        return TrafficSnapshot(
            dataset_id=self.dataset_id,
            snapshot_time=tc.peak_window,
            conditions=conditions,
            overall_avg_delay_minutes=round(avg_delay, 1),
            notes=tc.notes,
        )

    def demand_estimate(self) -> DemandEstimate:
        dc = self.demand_context
        zone_index = {z.zone_id: z for z in self.zones}

        zone_demands: list[ZoneDemand] = []
        total_capacity = 0
        for zone_id, zone_dc in dc.zones.items():
            utilization = (
                zone_dc.estimated_students / zone_dc.current_capacity
                if zone_dc.current_capacity > 0 else 0.0
            )
            zone_demands.append(ZoneDemand(
                zone_id=zone_id,
                zone_name=zone_index[zone_id].name if zone_id in zone_index else zone_id,
                estimated_students=zone_dc.estimated_students,
                current_capacity=zone_dc.current_capacity,
                utilization_pct=round(utilization * 100, 1),
                underserved=zone_dc.estimated_students > zone_dc.current_capacity,
            ))
            total_capacity += zone_dc.current_capacity

        overall_util = (
            dc.total_estimated_riders / total_capacity * 100
            if total_capacity > 0 else 0.0
        )

        return DemandEstimate(
            dataset_id=self.dataset_id,
            total_estimated_students=dc.total_estimated_riders,
            total_bus_capacity=total_capacity,
            overall_utilization_pct=round(overall_util, 1),
            zone_demand=zone_demands,
            demand_notes=dc.notes,
        )
