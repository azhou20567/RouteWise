from app.config import settings
from app.models.dataset import Dataset, Route
from app.models.metrics import MetricsDelta, RouteMetric, ScenarioMetrics


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _riders_for_route(route: Route, dataset: Dataset) -> int:
    """Sum estimated_riders across all stops that belong to this route."""
    stop_map = dataset.stop_map()
    return sum(stop_map[rs.stop_id].estimated_riders for rs in route.stops if rs.stop_id in stop_map)


def _route_metric(route: Route, dataset: Dataset) -> RouteMetric:
    riders = _riders_for_route(route, dataset)
    load_factor = riders / route.bus_capacity if route.bus_capacity > 0 else 0.0
    cost = route.total_distance_km * settings.cost_per_km_usd
    co2 = route.total_distance_km * settings.co2_per_km_kg
    return RouteMetric(
        route_id=route.route_id,
        route_name=route.name,
        color=route.color,
        num_stops=len(route.stops),
        bus_capacity=route.bus_capacity,
        estimated_riders=riders,
        load_factor=round(load_factor, 3),
        total_distance_km=route.total_distance_km,
        total_duration_minutes=route.total_duration_minutes,
        cost_usd=round(cost, 2),
        co2_kg=round(co2, 2),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_before(dataset: Dataset) -> ScenarioMetrics:
    route_metrics = [_route_metric(r, dataset) for r in dataset.routes]
    total_distance = sum(m.total_distance_km for m in route_metrics)
    total_duration = sum(m.total_duration_minutes for m in route_metrics)
    total_riders = sum(m.estimated_riders for m in route_metrics)
    avg_load = sum(m.load_factor for m in route_metrics) / len(route_metrics) if route_metrics else 0.0
    total_cost = sum(m.cost_usd for m in route_metrics)
    total_co2 = sum(m.co2_kg for m in route_metrics)

    return ScenarioMetrics(
        scenario="before",
        dataset_id=dataset.dataset_id,
        num_routes=len(route_metrics),
        total_distance_km=round(total_distance, 2),
        total_duration_minutes=round(total_duration, 1),
        total_riders=total_riders,
        avg_load_factor=round(avg_load, 3),
        total_cost_usd=round(total_cost, 2),
        total_co2_kg=round(total_co2, 2),
        route_metrics=route_metrics,
    )


def compute_after(dataset: Dataset) -> ScenarioMetrics:
    opt = dataset.optimized_scenario
    route_metrics = [_route_metric(r, dataset) for r in opt.routes]
    total_distance = sum(m.total_distance_km for m in route_metrics)
    total_duration = sum(m.total_duration_minutes for m in route_metrics)
    total_riders = sum(m.estimated_riders for m in route_metrics)
    avg_load = sum(m.load_factor for m in route_metrics) / len(route_metrics) if route_metrics else 0.0
    total_cost = sum(m.cost_usd for m in route_metrics)
    total_co2 = sum(m.co2_kg for m in route_metrics)

    return ScenarioMetrics(
        scenario="after",
        dataset_id=dataset.dataset_id,
        num_routes=len(route_metrics),
        total_distance_km=round(total_distance, 2),
        total_duration_minutes=round(total_duration, 1),
        total_riders=total_riders,
        avg_load_factor=round(avg_load, 3),
        total_cost_usd=round(total_cost, 2),
        total_co2_kg=round(total_co2, 2),
        route_metrics=route_metrics,
    )


def compute_delta(before: ScenarioMetrics, after: ScenarioMetrics) -> MetricsDelta:
    routes_eliminated = before.num_routes - after.num_routes
    distance_saved = before.total_distance_km - after.total_distance_km
    distance_saved_pct = (distance_saved / before.total_distance_km * 100) if before.total_distance_km else 0.0
    duration_saved = before.total_duration_minutes - after.total_duration_minutes
    cost_saved_daily = before.total_cost_usd - after.total_cost_usd
    cost_saved_pct = (cost_saved_daily / before.total_cost_usd * 100) if before.total_cost_usd else 0.0
    co2_saved_daily = before.total_co2_kg - after.total_co2_kg
    load_improvement = after.avg_load_factor - before.avg_load_factor

    # Annual savings: fleet reduction + distance-based fuel/operating savings
    fleet_savings = routes_eliminated * settings.annual_bus_operating_cost_usd
    distance_savings_annual = (
        distance_saved * settings.cost_per_km_usd * settings.daily_trips * settings.school_days_per_year
    )
    estimated_annual_savings = int(fleet_savings + distance_savings_annual)

    return MetricsDelta(
        routes_eliminated=routes_eliminated,
        distance_saved_km=round(distance_saved, 2),
        distance_saved_pct=round(distance_saved_pct, 1),
        duration_saved_minutes=round(duration_saved, 1),
        cost_saved_usd_daily=round(cost_saved_daily, 2),
        cost_saved_pct=round(cost_saved_pct, 1),
        co2_saved_kg_daily=round(co2_saved_daily, 2),
        load_factor_improvement=round(load_improvement, 3),
        estimated_annual_savings_usd=estimated_annual_savings,
    )
