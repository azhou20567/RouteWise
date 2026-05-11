from app.data.loader import get_dataset
from app.models.tool_outputs import DemandEstimate


async def get_demand_estimate(dataset_id: str) -> DemandEstimate:
    """
    Returns ridership demand estimates per zone based on proxy enrollment data,
    current bus capacity allocation, and utilization rates.

    Thin forwarder around the Dataset projection — see
    ``app.models.dataset.Dataset.demand_estimate`` for the implementation.
    """
    return get_dataset(dataset_id).demand_estimate()
