# CONTEXT.md

Project-specific vocabulary. When code, commit messages, PR descriptions, or
architecture reviews touch any of these concepts, prefer these names.

CLAUDE.md covers run instructions and high-level architecture; this file
defines the domain and module-level terms the codebase has settled on.

---

## Domain vocabulary

**Dataset** — A self-contained school + its routes + its stops + its
optimized counterpart + traffic/demand context. The runtime source of truth.
Loaded once from JSON at startup; treated as immutable.

**Route** — One bus's ordered visit through a sequence of Stops. Has a
capacity, a departure time, an `avg_load_factor`, and (planned) a road-snapped
encoded polyline `path`. A Route lives either in `Dataset.routes` (the
"before" scenario) or in `Dataset.optimized_scenario.routes` (the "after"
scenario).

**Stop** — A pickup location with `lat`, `lng`, `zone_id`, and
`estimated_riders`. Stops live in a flat pool on the Dataset; Routes
reference them by `stop_id` in their `RouteStop` sequence.

**Zone** — A polygonal slice of the school's catchment area, used to bucket
Stops and to attach `traffic_context` and `demand_context`.

**ScenarioMetrics** — Computed before/after roll-up: total distance,
duration, riders, average load factor, cost, CO₂, per-route metrics.
Pure function of a Dataset; lives in `app/services/metrics_service.py`.

**RouteRecommendation** — The structured output of an analysis run:
`analysis_summary`, `inefficiencies`, `route_edits`, `expected_improvements`,
`explanation`, `confidence_score`. The shape returned both by the LLM
agentic loop and by the heuristic recommender.

---

## Module-level vocabulary

**Dataset projection** — A method on the `Dataset` model that shapes one
slice of the Dataset for the LLM. Today: `Dataset.route_summary`,
`Dataset.traffic_snapshot`, `Dataset.demand_estimate`. These methods are the
single source of truth for "what the LLM sees about this dataset." The
FastAPI tools router, the MCP server, and the LLM agentic loop are all thin
adapters that call these projections — they do not reshape data themselves.

**Heuristic recommender** — `app/services/heuristic_recommender.py`. A pure
function that produces a `RouteRecommendation` from a Dataset + the
ScenarioMetrics triple. No LLM, no I/O, no API key. Used as the fallback
when `ANTHROPIC_API_KEY` is unset, and exercised directly by tests of the
underutilization rule. The "what makes a route a candidate for
consolidation" rule lives here and only here.

**LLM exit sentinel** — The role played by `generate_route_recommendation`
inside the agentic loop. Declared in `LLM_TOOLS` and recognised at
`llm_service.py`'s exit check, but **not** exposed via the FastAPI tools
router or the MCP server. When the LLM calls this tool, its `input` IS the
final RouteRecommendation; the loop terminates.

**Load-factor policy** — `settings.load_factor_underutilized` (default
0.50) and `settings.load_factor_good` (default 0.70) in `app/config.py`.
Single source of truth for both the heuristic recommender's threshold and
the LLM system prompt (which interpolates the underutilized threshold by
percentage).

**The four-tool pattern** — Historical: the codebase exposed four tools
including a phantom `generate_route_recommendation`. Now reduced to three
real data-gathering tools (`get_route_summary`, `get_traffic_snapshot`,
`get_demand_estimate`) plus the LLM exit sentinel. The `app/tools/*.py`
files are one-line forwarders around the corresponding Dataset projection;
they exist to give each tool a stable import path that the LLM, MCP, and
FastAPI adapters all use.

---

## Test surface

**`tests/conftest.py`** — Provides the `small_dataset` fixture: a minimal
in-memory Dataset (3 stops, 2 routes, 2 zones, 1 merged optimized route).
Tests should prefer this fixture over the bundled JSON datasets so they
remain unaffected by changes to real-world data.

**`tests/test_dataset_projections.py`** — Asserts the projection methods'
shape, ordering, and computed fields. No FastAPI, no MCP, no Anthropic.

**`tests/test_heuristic_recommender.py`** — Asserts the underutilization
rule and the RouteRecommendation shape produced without an LLM.
