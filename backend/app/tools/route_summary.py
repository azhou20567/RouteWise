from app.data.loader import get_dataset
from app.models.tool_outputs import RouteSummary, StopSummary


async def get_route_summary(dataset_id: str, route_id: str) -> RouteSummary:
    """
    Returns a detailed summary of a single bus route including stops,
    distance, duration, bus capacity, and estimated ridership load factor.
    """
    dataset = get_dataset(dataset_id)
    route = next((r for r in dataset.routes if r.route_id == route_id), None)
    if route is None:
        route_ids = [r.route_id for r in dataset.routes]
        raise ValueError(f"Route '{route_id}' not found. Available: {route_ids}")

    stop_map = dataset.stop_map()
    stops = []
    for rs in sorted(route.stops, key=lambda x: x.sequence):
        stop = stop_map.get(rs.stop_id)
        if stop:
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
        dataset_id=dataset_id,
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
