
from app.services.core.cohort.cohort_service import CohortService

service = CohortService()

def assign_user_cohort(profile: dict) -> str:
    return service.assign_cohort(profile)

def get_user_drift(user_id: str) -> dict:
    return service.get_cohort_drift(user_id)
