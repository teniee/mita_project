from app.services.core.cohort.cohort_analysis import determine_cohort
from app.services.core.cohort.cohort_cluster_engine import CohortClusterEngine
from app.services.core.cohort.cohort_drift_tracker import CohortDriftTracker
from app.services.core.cohort.cluster_mapper import map_cluster_label

class CohortService:
    def __init__(self):
        self.cluster_engine = CohortClusterEngine()
        self.drift_tracker = CohortDriftTracker()

    def assign_cohort(self, profile: dict) -> str:
        return determine_cohort(profile)

    def fit_clusters(self, user_blobs: dict):
        self.cluster_engine.fit(user_blobs)

    def get_user_cluster_label(self, user_id: str) -> str:
        label = self.cluster_engine.get_label(user_id)
        return map_cluster_label(label)

    def log_monthly_cohort(self, user_id: str, year: int, month: int, cohort: str):
        self.drift_tracker.log_month(user_id, year, month, cohort)

    def get_cohort_drift(self, user_id: str):
        return self.drift_tracker.get_drift(user_id)

    def get_current_cohort(self, user_id: str):
        return self.drift_tracker.get_current(user_id)

# 🔽 Functions below are used by API routes
_cohort_service = CohortService()

def assign_user_cohort(profile: dict) -> str:
    return _cohort_service.assign_cohort(profile)

def get_user_drift(user_id: str):
    return _cohort_service.get_cohort_drift(user_id)
