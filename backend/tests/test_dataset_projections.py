"""
Tests for Dataset projection methods — the single source of truth for
"what the LLM sees about this dataset." Each test exercises one method
in isolation; no FastAPI, no MCP, no Anthropic.
"""

import pytest

from app.models.tool_outputs import DemandEstimate, RouteSummary, TrafficSnapshot


def test_route_summary_orders_stops_by_sequence(small_dataset):
    summary = small_dataset.route_summary("R1")

    assert isinstance(summary, RouteSummary)
    assert summary.dataset_id == "test_ds"
    assert summary.route_id == "R1"
    assert [s.stop_id for s in summary.stops] == ["S1", "S2"]
    assert summary.num_stops == 2


def test_route_summary_computes_load_factor_from_stop_riders(small_dataset):
    summary = small_dataset.route_summary("R1")

    # S1 (8) + S2 (10) = 18 riders against capacity 72
    assert summary.estimated_riders == 18
    assert summary.bus_capacity == 72
    assert summary.avg_load_factor == round(18 / 72, 3)


def test_route_summary_raises_for_unknown_route(small_dataset):
    with pytest.raises(ValueError, match="Route 'R-NOPE' not found"):
        small_dataset.route_summary("R-NOPE")


def test_traffic_snapshot_includes_one_condition_per_zone(small_dataset):
    snap = small_dataset.traffic_snapshot()

    assert isinstance(snap, TrafficSnapshot)
    assert snap.snapshot_time == "07:00-09:00"
    assert {c.zone_id for c in snap.conditions} == {"Z1", "Z2"}
    z1 = next(c for c in snap.conditions if c.zone_id == "Z1")
    assert z1.zone_name == "North"
    assert z1.congestion_level == "medium"


def test_traffic_snapshot_average_delay_is_mean_of_zone_delays(small_dataset):
    snap = small_dataset.traffic_snapshot()
    # (4.0 + 2.0) / 2 = 3.0
    assert snap.overall_avg_delay_minutes == 3.0


def test_demand_estimate_flags_underserved_zones(small_dataset):
    demand = small_dataset.demand_estimate()

    assert isinstance(demand, DemandEstimate)
    by_zone = {z.zone_id: z for z in demand.zone_demand}
    # Z1: 80 students vs 72 capacity → underserved
    assert by_zone["Z1"].underserved is True
    # Z2: 60 students vs 72 capacity → not underserved
    assert by_zone["Z2"].underserved is False


def test_demand_estimate_total_capacity_sums_zones(small_dataset):
    demand = small_dataset.demand_estimate()
    assert demand.total_bus_capacity == 72 + 72
    assert demand.total_estimated_students == 140
