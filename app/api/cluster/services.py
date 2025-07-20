from app.services.core.cohort.cohort_cluster_engine import CohortClusterEngine

engine = CohortClusterEngine()


def fit_cluster_model(user_data: list):
    return engine.fit(user_data)


def get_user_cluster_label(user_id: str):
    return engine.get_label(user_id)


def get_cluster_centroids():
    return engine.get_centroids()
