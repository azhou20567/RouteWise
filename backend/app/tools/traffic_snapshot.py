from app.data.loader import get_dataset
from app.models.tool_outputs import TrafficSnapshot, TrafficCondition


async def get_traffic_snapshot(dataset_id: str) -> TrafficSnapshot:
    """
    Returns simulated morning peak traffic conditions for all zones in the
    dataset, including congestion level and estimated delay per zone.
    These are pre-modeled from historical patterns and route timing data.
    """
    dataset = get_dataset(dataset_id)
    tc = dataset.traffic_context
    zone_map = {z.zone_id: z for z in dataset.zones}

    conditions = []
    for zone_id, zone_tc in tc.zones.items():
        zone = zone_map.get(zone_id)
        conditions.append(TrafficCondition(
            zone_id=zone_id,
            zone_name=zone.name if zone else zone_id,
            congestion_level=zone_tc.congestion_level,
            peak_delay_minutes=zone_tc.peak_delay_minutes,
        ))

    avg_delay = (
        sum(c.peak_delay_minutes for c in conditions) / len(conditions)
        if conditions else 0.0
    )

    return TrafficSnapshot(
        dataset_id=dataset_id,
        snapshot_time=tc.peak_window,
        conditions=conditions,
        overall_avg_delay_minutes=round(avg_delay, 1),
        notes=tc.notes,
    )
