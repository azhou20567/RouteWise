import json
from functools import lru_cache
from pathlib import Path

from app.config import settings
from app.models.dataset import Dataset


@lru_cache(maxsize=None)
def _load_all() -> dict[str, Dataset]:
    """Load and cache all dataset JSON files from the datasets directory."""
    datasets: dict[str, Dataset] = {}
    dataset_dir: Path = settings.dataset_dir

    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

    for path in sorted(dataset_dir.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        ds = Dataset.model_validate(raw)
        datasets[ds.dataset_id] = ds

    return datasets


def get_dataset(dataset_id: str) -> Dataset:
    all_datasets = _load_all()
    if dataset_id not in all_datasets:
        raise KeyError(f"Dataset '{dataset_id}' not found. Available: {list(all_datasets)}")
    return all_datasets[dataset_id]


def list_datasets() -> list[Dataset]:
    return list(_load_all().values())


def reload() -> None:
    """Clear the cache so datasets are re-read from disk (useful in tests)."""
    _load_all.cache_clear()
