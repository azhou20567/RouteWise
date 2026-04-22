from pydantic import BaseModel, Field
from typing import Optional, Literal


class RouteEdit(BaseModel):
    action: Literal["merge", "eliminate", "restructure", "adjust_timing"]
    affected_routes: list[str]
    rationale: str
    estimated_distance_saving_km: Optional[float] = None


class ExpectedImprovement(BaseModel):
    metric: str
    before_value: float
    after_value: float
    unit: str
    improvement_pct: float


class RouteRecommendation(BaseModel):
    dataset_id: str
    analysis_summary: str
    inefficiencies: list[str]
    route_edits: list[RouteEdit]
    expected_improvements: list[ExpectedImprovement]
    explanation: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    model_used: str = "claude-sonnet-4-6"
