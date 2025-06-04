from pydantic import BaseModel
from typing import List, Dict, Any


class FitRequest(BaseModel):
    user_data: List[Dict[str, float]]  # массив пользователей с признаками


class LabelRequest(BaseModel):
    user_id: str  # ID пользователя для предсказания кластера


class ClusterResult(BaseModel):
    cluster_id: int
    cluster_size: int
    inertia: float
    label_distribution: Dict[str, int]


class LabelResult(BaseModel):
    user_id: str
    cluster_id: int
    label: str  # строковое описание (например, "spender", "saver")


class CentroidResult(BaseModel):
    cluster_id: int
    centroid: Dict[str, float]  # координаты центра кластера по признакам
