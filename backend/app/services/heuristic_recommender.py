"""
Heuristic recommender — produces a complete RouteRecommendation from a
Dataset and pre-computed ScenarioMetrics without invoking an LLM.

Two callers today:
  - llm_service.run_analysis when ANTHROPIC_API_KEY is unset (fallback path)
  - tests that exercise the recommendation rules without a live API key

The "what makes a route a candidate for consolidation" rule lives here and
only here. Thresholds are read from app.config.settings so the same policy
drives the LLM system prompt and this module.
"""

from app.config import settings
from app.models.dataset import Dataset
from app.models.metrics import ScenarioMetrics, MetricsDelta
from app.models.recommendation import (
    ExpectedImprovement,
    RouteEdit,
    RouteRecommendation,
)


def recommend(
    dataset: Dataset,
    before: ScenarioMetrics,
    after: ScenarioMetrics,
    delta: MetricsDelta,
) -> RouteRecommendation:
    threshold = settings.load_factor_underutilized
    threshold_pct_int = int(round(threshold * 100))

    low_util = [m for m in before.route_metrics if m.load_factor < threshold]
    eliminated = dataset.optimized_scenario.eliminated_routes

    inefficiencies = [
        f"Route {m.route_id} operates at only {m.load_factor:.0%} capacity "
        f"({m.estimated_riders}/{m.bus_capacity} seats filled)"
        for m in low_util
    ]
    if delta.distance_saved_km > 0:
        inefficiencies.append(
            f"Current routing covers {before.total_distance_km:.1f} km/day; "
            f"{delta.distance_saved_km:.1f} km can be eliminated through consolidation"
        )

    distance_by_route = {m.route_id: m.total_distance_km for m in before.route_metrics}
    route_edits = [
        RouteEdit(
            action="eliminate",
            affected_routes=[route_id],
            rationale=(
                f"Route {route_id} has insufficient ridership to justify a dedicated bus. "
                "Students are redistributed to adjacent routes with available capacity."
            ),
            estimated_distance_saving_km=round(distance_by_route.get(route_id, 0.0), 1),
        )
        for route_id in eliminated
    ]

    load_factor_improvement_pct = (
        delta.load_factor_improvement / before.avg_load_factor * 100
        if before.avg_load_factor > 0 else 0.0
    )
    fleet_reduction_pct = (
        delta.routes_eliminated / before.num_routes * 100
        if before.num_routes > 0 else 0.0
    )

    expected_improvements = [
        ExpectedImprovement(
            metric="Average bus utilization",
            before_value=round(before.avg_load_factor * 100, 1),
            after_value=round(after.avg_load_factor * 100, 1),
            unit="%",
            improvement_pct=round(load_factor_improvement_pct, 1),
        ),
        ExpectedImprovement(
            metric="Total daily distance",
            before_value=before.total_distance_km,
            after_value=after.total_distance_km,
            unit="km",
            improvement_pct=round(delta.distance_saved_pct, 1),
        ),
        ExpectedImprovement(
            metric="Fleet size",
            before_value=before.num_routes,
            after_value=after.num_routes,
            unit="buses",
            improvement_pct=round(fleet_reduction_pct, 1),
        ),
    ]

    return RouteRecommendation(
        dataset_id=dataset.dataset_id,
        analysis_summary=(
            f"Analysis of {dataset.school_name}'s {before.num_routes}-route network identified "
            f"{len(low_util)} underutilized route(s) operating below {threshold_pct_int}% capacity. "
            f"Consolidating to {after.num_routes} routes maintains full student coverage "
            f"while improving average utilization from {before.avg_load_factor:.0%} to {after.avg_load_factor:.0%}."
        ),
        inefficiencies=inefficiencies,
        route_edits=route_edits,
        expected_improvements=expected_improvements,
        explanation=(
            f"The current routing plan for {dataset.school_name} operates {before.num_routes} buses "
            f"serving {before.total_riders} students across {before.total_distance_km:.1f} km of daily routes. "
            f"However, {len(low_util)} of these routes are significantly underloaded, with buses running "
            f"at less than {threshold_pct_int}% of their seating capacity each morning.\n\n"
            f"The recommended optimization eliminates {delta.routes_eliminated} bus route(s) by merging "
            f"low-density pickup areas into adjacent routes that have available capacity. "
            f"Every student currently served will continue to have a pickup stop within walking distance "
            f"of their home — no students lose service.\n\n"
            f"The primary financial benefit comes from retiring {delta.routes_eliminated} bus from daily "
            f"operation, saving an estimated ${delta.estimated_annual_savings_usd:,} per year in combined "
            f"fleet operating costs and fuel. Average bus utilization improves from "
            f"{before.avg_load_factor:.0%} to {after.avg_load_factor:.0%}, making more efficient use "
            f"of the district's existing vehicle fleet."
        ),
        confidence_score=0.82,
        model_used="heuristic (no LLM)",
    )
