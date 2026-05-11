from app.data.loader import get_dataset
from app.models.tool_outputs import RouteSummary


async def get_route_summary(dataset_id: str, route_id: str) -> RouteSummary:
    """
    Returns a detailed summary of a single bus route including stops,
    distance, duration, bus capacity, and estimated ridership load factor.

    Thin forwarder around the Dataset projection — see
    ``app.models.dataset.Dataset.route_summary`` for the implementation.
    """
    return get_dataset(dataset_id).route_summary(route_id)
