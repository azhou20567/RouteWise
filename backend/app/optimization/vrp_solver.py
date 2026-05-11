"""
Capacitated Vehicle Routing solver via OR-Tools.

Cost model (Q5(d) from the grilled plan): lexicographic
  1. Minimize the number of buses used
  2. Among solutions with the minimum bus count, minimize total distance

This is achieved by giving every bus a very high `fixed_cost_of_vehicle`
relative to the per-meter arc cost. The solver prefers leaving a bus
unused when it can, then optimizes routing for the buses it does use.

The solver is purposely fed a `max_vehicles` that is generous (typically
the current "before" route count) — we let it pick fewer rather than
prescribing the consolidation outcome.

This module is build-time only. The runtime API never imports OR-Tools.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.google_maps_service import LatLng


@dataclass(frozen=True)
class VrpStop:
    """A stop the solver must visit, plus how many riders board there."""
    stop_id: str
    location: LatLng
    riders: int


@dataclass(frozen=True)
class VrpSolution:
    """One solver output route: ordered stop_ids, with totals."""
    stop_ids: list[str]
    total_distance_m: float
    total_duration_s: float
    total_riders: int


@dataclass(frozen=True)
class VrpResult:
    """All routes produced. `unused_vehicles` is the headline consolidation."""
    routes: list[VrpSolution]
    unused_vehicles: int
    objective_value: int


def solve_cvrp(
    school: LatLng,
    stops: list[VrpStop],
    distance_matrix_m: list[list[float]],
    duration_matrix_s: list[list[float]],
    *,
    max_vehicles: int,
    bus_capacity: int,
    fixed_cost_per_vehicle: int = 1_000_000,
    time_limit_seconds: int = 30,
) -> VrpResult:
    """
    Solve a school-bus CVRP where every route starts and ends at the
    school. Node 0 in the matrices is the school; nodes 1..N are stops.

    `distance_matrix_m[i][j]` must be the road distance from node i to
    node j in meters (matches `GoogleMapsService.distance_matrix` output).
    `duration_matrix_s` is the matching duration, used for the
    `total_duration_s` field on each returned VrpSolution.

    The objective is lex-min (vehicles, distance) — see module docstring.
    """
    # Lazy import so server runtime doesn't need OR-Tools installed.
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2  # type: ignore[import-not-found]

    num_nodes = 1 + len(stops)               # school + stops
    if len(distance_matrix_m) != num_nodes:
        raise ValueError(
            f"distance_matrix must be {num_nodes}x{num_nodes}, got "
            f"{len(distance_matrix_m)}x{len(distance_matrix_m[0]) if distance_matrix_m else 0}"
        )

    demands = [0] + [s.riders for s in stops]
    starts = [0] * max_vehicles
    ends = [0] * max_vehicles

    manager = pywrapcp.RoutingIndexManager(num_nodes, max_vehicles, starts, ends)
    routing = pywrapcp.RoutingModel(manager)

    # Distance callback (returns integer meters — OR-Tools wants int)
    def distance_callback(from_index: int, to_index: int) -> int:
        i = manager.IndexToNode(from_index)
        j = manager.IndexToNode(to_index)
        return int(round(distance_matrix_m[i][j]))

    transit_idx = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

    # Capacity dimension — riders boarded per route capped at bus_capacity
    def demand_callback(from_index: int) -> int:
        return demands[manager.IndexToNode(from_index)]

    demand_idx = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_idx,
        0,
        [bus_capacity] * max_vehicles,
        True,                              # start_cumul_to_zero
        "Capacity",
    )

    # Lex-min (vehicles, distance): heavy fixed cost per used vehicle
    for v in range(max_vehicles):
        routing.SetFixedCostOfVehicle(fixed_cost_per_vehicle, v)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = time_limit_seconds

    solution = routing.SolveWithParameters(params)
    if solution is None:
        raise RuntimeError("OR-Tools VRP solver found no solution")

    routes: list[VrpSolution] = []
    unused = 0
    for v in range(max_vehicles):
        index = routing.Start(v)
        if routing.IsEnd(solution.Value(routing.NextVar(index))):
            unused += 1
            continue

        stop_ids: list[str] = []
        total_dist = 0.0
        total_dur = 0.0
        total_riders = 0
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != 0:                  # skip school
                stop_ids.append(stops[node - 1].stop_id)
                total_riders += stops[node - 1].riders
            next_index = solution.Value(routing.NextVar(index))
            next_node = manager.IndexToNode(next_index)
            total_dist += distance_matrix_m[node][next_node]
            total_dur += duration_matrix_s[node][next_node]
            index = next_index

        routes.append(VrpSolution(
            stop_ids=stop_ids,
            total_distance_m=total_dist,
            total_duration_s=total_dur,
            total_riders=total_riders,
        ))

    return VrpResult(
        routes=routes,
        unused_vehicles=unused,
        objective_value=solution.ObjectiveValue(),
    )


def zone_naive_partition(stops: list[VrpStop], zone_for_stop: dict[str, str]) -> list[VrpSolution]:
    """
    Build the "before" baseline: one route per zone, stops visited in
    their input order, no optimization. Used to show what the solver
    improves on. Distance/duration fields are left at 0 — the build
    script fills them in via the Directions API once the route order
    is final.
    """
    by_zone: dict[str, list[VrpStop]] = {}
    for s in stops:
        by_zone.setdefault(zone_for_stop[s.stop_id], []).append(s)

    out: list[VrpSolution] = []
    for zone_id in sorted(by_zone):
        zone_stops = by_zone[zone_id]
        out.append(VrpSolution(
            stop_ids=[s.stop_id for s in zone_stops],
            total_distance_m=0.0,
            total_duration_s=0.0,
            total_riders=sum(s.riders for s in zone_stops),
        ))
    return out
