from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.data.loader import get_dataset, list_datasets
from app.models.dataset import Dataset

router = APIRouter(prefix="/datasets", tags=["datasets"])


class DatasetMeta(BaseModel):
    dataset_id: str
    name: str
    school_name: str
    school_level: str
    school_lat: float
    school_lng: float
    num_routes_before: int
    num_routes_after: int
    total_stops: int


@router.get("", response_model=list[DatasetMeta])
async def list_all_datasets():
    """List available datasets (lightweight metadata only)."""
    datasets = list_datasets()
    return [
        DatasetMeta(
            dataset_id=ds.dataset_id,
            name=ds.name,
            school_name=ds.school_name,
            school_level=ds.school_level,
            school_lat=ds.school_lat,
            school_lng=ds.school_lng,
            num_routes_before=len(ds.routes),
            num_routes_after=len(ds.optimized_scenario.routes),
            total_stops=len(ds.stops),
        )
        for ds in datasets
    ]


@router.get("/{dataset_id}", response_model=Dataset)
async def get_one_dataset(dataset_id: str):
    """Return the full dataset including routes, stops, zones, and optimized scenario."""
    try:
        return get_dataset(dataset_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
