from app.models.recommendation import RouteRecommendation
from app.services.llm_service import run_analysis


async def generate_route_recommendation(dataset_id: str) -> RouteRecommendation:
    """
    Runs the full LLM agentic analysis loop and returns a structured
    RouteRecommendation. Falls back to a static recommendation if
    ANTHROPIC_API_KEY is not configured.

    This function is the shared implementation called by:
      - FastAPI router (POST /analysis/{dataset_id})
      - MCP server tool handler
    """
    return await run_analysis(dataset_id)
