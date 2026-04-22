"""
LLM agentic loop using Claude with tool_use for structured route analysis.

Claude is given 3 data-gathering tools and 1 exit tool:
  get_route_summary       → call once per route
  get_traffic_snapshot    → call once
  get_demand_estimate     → call once
  generate_route_recommendation → FINAL call, terminates the loop

When generate_route_recommendation is called, its input IS the structured
RouteRecommendation that gets returned to the caller.
"""

import logging
from anthropic import AsyncAnthropic, APIStatusError

from app.config import settings
from app.data.loader import get_dataset
from app.models.recommendation import RouteRecommendation, RouteEdit, ExpectedImprovement
from app.tools.route_summary import get_route_summary
from app.tools.traffic_snapshot import get_traffic_snapshot
from app.tools.demand_estimate import get_demand_estimate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions sent to Claude
# ---------------------------------------------------------------------------

LLM_TOOLS = [
    {
        "name": "get_route_summary",
        "description": (
            "Returns a detailed summary of a single bus route including its stops, "
            "total distance, duration, bus capacity, and estimated ridership load factor. "
            "Call this for EACH route you want to analyze."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "Dataset identifier"},
                "route_id":   {"type": "string", "description": "Route identifier to summarize"},
            },
            "required": ["dataset_id", "route_id"],
        },
    },
    {
        "name": "get_traffic_snapshot",
        "description": (
            "Returns simulated morning peak traffic conditions by zone, "
            "including congestion level and estimated delay minutes. Call this once."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "Dataset identifier"},
            },
            "required": ["dataset_id"],
        },
    },
    {
        "name": "get_demand_estimate",
        "description": (
            "Returns ridership demand estimates per zone: enrolled students, "
            "current bus capacity, and utilization percentage. Call this once."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "Dataset identifier"},
            },
            "required": ["dataset_id"],
        },
    },
    {
        "name": "generate_route_recommendation",
        "description": (
            "FINAL STEP — call this exactly once after gathering all route, traffic, "
            "and demand data. Provide your complete structured recommendation. "
            "This terminates the analysis loop."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "analysis_summary": {
                    "type": "string",
                    "description": "2–3 sentence executive summary for a school district administrator",
                },
                "inefficiencies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific inefficiencies found, one per string",
                },
                "route_edits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["merge", "eliminate", "restructure", "adjust_timing"],
                            },
                            "affected_routes": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "rationale": {"type": "string"},
                            "estimated_distance_saving_km": {"type": "number"},
                        },
                        "required": ["action", "affected_routes", "rationale"],
                    },
                },
                "expected_improvements": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "metric":          {"type": "string"},
                            "before_value":    {"type": "number"},
                            "after_value":     {"type": "number"},
                            "unit":            {"type": "string"},
                            "improvement_pct": {"type": "number"},
                        },
                        "required": ["metric", "before_value", "after_value", "unit", "improvement_pct"],
                    },
                },
                "explanation": {
                    "type": "string",
                    "description": (
                        "Plain-English 3–5 paragraph narrative explaining the analysis, "
                        "proposed changes, and expected impact for school administrators"
                    ),
                },
                "confidence_score": {
                    "type": "number",
                    "description": "Confidence in recommendations, 0.0 to 1.0",
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
            },
            "required": [
                "analysis_summary", "inefficiencies", "route_edits",
                "expected_improvements", "explanation", "confidence_score",
            ],
        },
    },
]

SYSTEM_PROMPT = """\
You are an expert school bus route optimization analyst for a school district in Bellevue, Washington.
Your goal is to analyze the provided route data and generate specific, actionable recommendations
to improve fleet utilization and reduce operating costs.

Workflow:
1. Call get_route_summary for EACH route listed in the initial message.
2. Call get_traffic_snapshot once to understand peak-hour conditions.
3. Call get_demand_estimate once to understand ridership demand by zone.
4. Call generate_route_recommendation ONCE with your complete structured analysis.

Analysis guidelines:
- Routes below 50% load factor are strong candidates for consolidation or elimination.
- When merging routes, verify the combined stop count can be served within a reasonable time window.
- Traffic conditions affect feasibility of longer merged routes — factor in delay data.
- All recommendations must maintain full coverage for every student currently served.
- Quantify improvements with specific numbers drawn from the data you gathered.
- Write the explanation field for a school district administrator, not a routing engineer.
- Be direct and specific about which routes to change and why.
"""


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

async def _dispatch(tool_name: str, tool_input: dict) -> str:
    if tool_name == "get_route_summary":
        result = await get_route_summary(**tool_input)
    elif tool_name == "get_traffic_snapshot":
        result = await get_traffic_snapshot(**tool_input)
    elif tool_name == "get_demand_estimate":
        result = await get_demand_estimate(**tool_input)
    else:
        raise ValueError(f"Unknown tool: {tool_name}")
    return result.model_dump_json()


# ---------------------------------------------------------------------------
# Fallback (no API key configured)
# ---------------------------------------------------------------------------

def _fallback_recommendation(dataset_id: str) -> RouteRecommendation:
    """
    Returns a static recommendation derived directly from dataset metrics.
    Used when ANTHROPIC_API_KEY is not configured — keeps the demo functional
    without a live LLM call.
    """
    from app.services.metrics_service import compute_before, compute_after, compute_delta

    dataset = get_dataset(dataset_id)
    before = compute_before(dataset)
    after = compute_after(dataset)
    delta = compute_delta(before, after)

    low_util = [m for m in before.route_metrics if m.load_factor < 0.5]
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

    route_edits = []
    for route_id in eliminated:
        route_edits.append(RouteEdit(
            action="eliminate",
            affected_routes=[route_id],
            rationale=(
                f"Route {route_id} has insufficient ridership to justify a dedicated bus. "
                "Students are redistributed to adjacent routes with available capacity."
            ),
            estimated_distance_saving_km=round(
                next((m.total_distance_km for m in before.route_metrics if m.route_id == route_id), 0), 1
            ),
        ))

    expected_improvements = [
        ExpectedImprovement(
            metric="Average bus utilization",
            before_value=round(before.avg_load_factor * 100, 1),
            after_value=round(after.avg_load_factor * 100, 1),
            unit="%",
            improvement_pct=round(delta.load_factor_improvement / before.avg_load_factor * 100, 1),
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
            improvement_pct=round(delta.routes_eliminated / before.num_routes * 100, 1),
        ),
    ]

    return RouteRecommendation(
        dataset_id=dataset_id,
        analysis_summary=(
            f"Analysis of {dataset.school_name}'s {before.num_routes}-route network identified "
            f"{len(low_util)} underutilized route(s) operating below 50% capacity. "
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
            f"at less than half their seating capacity each morning.\n\n"
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
        model_used="fallback (no API key configured)",
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run_analysis(dataset_id: str) -> RouteRecommendation:
    """
    Runs the full agentic analysis loop. Falls back to a static recommendation
    if ANTHROPIC_API_KEY is not configured.
    """
    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY not set — using fallback recommendation")
        return _fallback_recommendation(dataset_id)

    dataset = get_dataset(dataset_id)
    route_ids = [r.route_id for r in dataset.routes]

    user_message = (
        f"Analyze bus routes for {dataset.school_name} (school level: {dataset.school_level}, "
        f"dataset ID: {dataset_id}).\n\n"
        f"There are {len(route_ids)} routes to analyze: {', '.join(route_ids)}.\n\n"
        f"Please call get_route_summary for each route, then get_traffic_snapshot, "
        f"then get_demand_estimate, and finally generate_route_recommendation."
    )

    messages: list[dict] = [{"role": "user", "content": user_message}]
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    for turn in range(settings.max_tool_turns):
        response = await client.messages.create(
            model=settings.model_name,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=LLM_TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            raise RuntimeError("Claude stopped without calling generate_route_recommendation")

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                if block.name == "generate_route_recommendation":
                    data = {**block.input, "dataset_id": dataset_id, "model_used": settings.model_name}
                    return RouteRecommendation.model_validate(data)

                try:
                    result_str = await _dispatch(block.name, block.input)
                except Exception as exc:
                    result_str = f"Error: {exc}"
                    logger.exception("Tool %s failed", block.name)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                })

            if tool_results:
                messages.append({"role": "user", "content": tool_results})

    raise RuntimeError(f"Max tool turns ({settings.max_tool_turns}) exceeded without recommendation")
