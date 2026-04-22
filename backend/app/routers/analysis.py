from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.data.loader import get_dataset
from app.models.metrics import MetricsDelta, ScenarioMetrics
from app.models.recommendation import RouteRecommendation
from app.services.llm_service import run_analysis
from app.services.metrics_service import compute_after, compute_before, compute_delta

router = APIRouter(prefix="/analysis", tags=["analysis"])


class MetricsResponse(BaseModel):
    before: ScenarioMetrics
    after: ScenarioMetrics
    delta: MetricsDelta


class AnalysisResponse(BaseModel):
    recommendation: RouteRecommendation
    before: ScenarioMetrics
    after: ScenarioMetrics
    delta: MetricsDelta


@router.get("/{dataset_id}/metrics", response_model=MetricsResponse)
async def get_metrics(dataset_id: str):
    """
    Compute before/after metrics for a dataset without calling the LLM.
    Fast — use this to populate the metrics panel on initial load.
    """
    try:
        dataset = get_dataset(dataset_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    before = compute_before(dataset)
    after = compute_after(dataset)
    delta = compute_delta(before, after)
    return MetricsResponse(before=before, after=after, delta=delta)


@router.post("/{dataset_id}/recommend", response_model=AnalysisResponse)
async def recommend(dataset_id: str):
    """
    Run the full LLM analysis and return a structured recommendation
    alongside computed before/after metrics. Slow (~10–20 s with live LLM).
    Falls back to a static recommendation if ANTHROPIC_API_KEY is not set.
    """
    try:
        dataset = get_dataset(dataset_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        recommendation = await run_analysis(dataset_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM analysis failed: {exc}")

    before = compute_before(dataset)
    after = compute_after(dataset)
    delta = compute_delta(before, after)

    return AnalysisResponse(
        recommendation=recommendation,
        before=before,
        after=after,
        delta=delta,
    )
