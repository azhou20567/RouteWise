from app.data.loader import get_dataset
from app.models.tool_outputs import DemandEstimate, ZoneDemand


async def get_demand_estimate(dataset_id: str) -> DemandEstimate:
    """
    Returns ridership demand estimates per zone based on proxy enrollment data,
    current bus capacity allocation, and utilization rates.
    Underserved zones have estimated_students > current_capacity.
    """
    dataset = get_dataset(dataset_id)
    dc = dataset.demand_context
    zone_map = {z.zone_id: z for z in dataset.zones}

    zone_demand_list: list[ZoneDemand] = []
    total_capacity = 0

    for zone_id, zone_dc in dc.zones.items():
        zone = zone_map.get(zone_id)
        utilization = (
            zone_dc.estimated_students / zone_dc.current_capacity
            if zone_dc.current_capacity > 0 else 0.0
        )
        zone_demand_list.append(ZoneDemand(
            zone_id=zone_id,
            zone_name=zone.name if zone else zone_id,
            estimated_students=zone_dc.estimated_students,
            current_capacity=zone_dc.current_capacity,
            utilization_pct=round(utilization * 100, 1),
            underserved=zone_dc.estimated_students > zone_dc.current_capacity,
        ))
        total_capacity += zone_dc.current_capacity

    overall_util = (
        dc.total_estimated_riders / total_capacity * 100
        if total_capacity > 0 else 0.0
    )

    return DemandEstimate(
        dataset_id=dataset_id,
        total_estimated_students=dc.total_estimated_riders,
        total_bus_capacity=total_capacity,
        overall_utilization_pct=round(overall_util, 1),
        zone_demand=zone_demand_list,
        demand_notes=dc.notes,
    )
