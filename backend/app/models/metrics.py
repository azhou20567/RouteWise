from pydantic import BaseModel


class RouteMetric(BaseModel):
    route_id: str
    route_name: str
    color: str
    num_stops: int
    bus_capacity: int
    estimated_riders: int
    load_factor: float
    total_distance_km: float
    total_duration_minutes: float
    cost_usd: float
    co2_kg: float


class ScenarioMetrics(BaseModel):
    scenario: str                    # "before" | "after"
    dataset_id: str
    num_routes: int
    total_distance_km: float
    total_duration_minutes: float
    total_riders: int
    avg_load_factor: float
    total_cost_usd: float
    total_co2_kg: float
    route_metrics: list[RouteMetric]


class MetricsDelta(BaseModel):
    routes_eliminated: int
    distance_saved_km: float
    distance_saved_pct: float
    duration_saved_minutes: float
    cost_saved_usd_daily: float
    cost_saved_pct: float
    co2_saved_kg_daily: float
    load_factor_improvement: float   # after - before (absolute)
    estimated_annual_savings_usd: int
