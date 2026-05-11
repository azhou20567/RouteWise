"""
LLM agentic loop using Claude with tool_use for structured route analysis.

Claude is given 3 data-gathering tools and 1 exit sentinel:
  get_route_summary       → call once per route
  get_traffic_snapshot    → call once
  get_demand_estimate     → call once
  generate_route_recommendation → FINAL call, terminates the loop

`generate_route_recommendation` is an LLM-only sentinel — its schema is
declared here and the loop recognises it as the exit. It is intentionally
not exposed via the FastAPI tools router or the MCP server. When the LLM
calls it, the `input` IS the structured RouteRecommendation returned to
the caller.

When ANTHROPIC_API_KEY is unset, the no-key path skips the loop entirely
and delegates to app.services.heuristic_recommender — the same module a
test would import to exercise the consolidation rule without a live API.
"""

import logging
from anthropic import AsyncAnthropic

from app.config import settings
from app.data.loader import get_dataset
from app.models.recommendation import RouteRecommendation
from app.services import heuristic_recommender
from app.services.metrics_service import compute_after, compute_before, compute_delta
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

_UNDERUTILIZED_PCT = int(round(settings.load_factor_underutilized * 100))

SYSTEM_PROMPT = f"""\
You are an expert school bus route optimization analyst for a school district in Bellevue, Washington.
Your goal is to analyze the provided route data and generate specific, actionable recommendations
to improve fleet utilization and reduce operating costs.

Workflow:
1. Call get_route_summary for EACH route listed in the initial message.
2. Call get_traffic_snapshot once to understand peak-hour conditions.
3. Call get_demand_estimate once to understand ridership demand by zone.
4. Call generate_route_recommendation ONCE with your complete structured analysis.

Analysis guidelines:
- Routes below {_UNDERUTILIZED_PCT}% load factor are strong candidates for consolidation or elimination.
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
# Main entry point
# ---------------------------------------------------------------------------

async def run_analysis(dataset_id: str) -> RouteRecommendation:
    """
    Runs the full agentic analysis loop. Falls back to the heuristic
    recommender if ANTHROPIC_API_KEY is not configured.
    """
    dataset = get_dataset(dataset_id)

    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY not set — using heuristic recommender")
        before = compute_before(dataset)
        after = compute_after(dataset)
        delta = compute_delta(before, after)
        return heuristic_recommender.recommend(dataset, before, after, delta)

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
