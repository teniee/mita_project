from typing import Any, Dict, List

from pydantic import BaseModel


class FitRequest(BaseModel):
    user_data: List[Dict[str, float]]  # array of users with features


class LabelRequest(BaseModel):
    user_id: str  # user ID for cluster prediction


class ClusterResult(BaseModel):
    cluster_id: int
    cluster_size: int
    inertia: float
    label_distribution: Dict[str, int]


class LabelResult(BaseModel):
    user_id: str
    cluster_id: int
    label: str  # descriptive label (e.g., "spender", "saver")


class CentroidResult(BaseModel):
    cluster_id: int
    centroid: Dict[str, float]  # centroid coordinates by features
