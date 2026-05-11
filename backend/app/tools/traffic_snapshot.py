from app.data.loader import get_dataset
from app.models.tool_outputs import TrafficSnapshot


async def get_traffic_snapshot(dataset_id: str) -> TrafficSnapshot:
    """
    Returns simulated morning peak traffic conditions for all zones in the
    dataset, including congestion level and estimated delay per zone.

    Thin forwarder around the Dataset projection — see
    ``app.models.dataset.Dataset.traffic_snapshot`` for the implementation.
    """
    return get_dataset(dataset_id).traffic_snapshot()
