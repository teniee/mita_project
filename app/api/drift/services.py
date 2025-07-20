from app.services.core.cohort.cohort_drift_tracker import CohortDriftTracker

drifter = CohortDriftTracker()


def log_cohort_drift(data: dict):
    return drifter.log_month(**data)


def get_cohort_drift(data: dict):
    return drifter.get_drift(**data)
