from app.services.core.cohort.cluster_mapper import map_cluster_label
from app.services.core.cohort.cohort_cluster_engine import CohortClusterEngine

# Create a single cluster engine instance for the app
_cluster_engine = CohortClusterEngine()


def fit_cluster_model(user_blobs: dict) -> None:
    """Train the clusterer on user feature data."""
    _cluster_engine.fit(user_blobs)


def get_user_cluster_label(user_id: str) -> str:
    """Return cluster label for the given user ID."""
    label = _cluster_engine.get_label(user_id)
    return map_cluster_label(label)


def get_cluster_centroids() -> dict:
    """Return centroid coordinates for all clusters."""
    return _cluster_engine.get_centroids()
