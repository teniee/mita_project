import json
import os
from typing import Dict

import firebase_admin
from firebase_admin import credentials, firestore

# Get JSON key from environment variable
firebase_json = os.environ.get("FIREBASE_JSON")

_COLLECTION = "drift_logs"


def _get_db():
    if not firebase_admin._apps:
        if firebase_json:
            cred = credentials.Certificate(json.loads(firebase_json))
        else:
            cred_path = os.getenv("GOOGLE_SERVICE_ACCOUNT") or os.getenv(
                "GOOGLE_APPLICATION_CREDENTIALS"
            )
            if cred_path and os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
            else:
                cred = credentials.ApplicationDefault()

        firebase_admin.initialize_app(cred)

    return firestore.client()



def log_cohort_drift(user_id: str, month: str, value: float) -> Dict:
    """Log or update the user's drift value in Firestore."""
    db = _get_db()
    doc_id = f"{user_id}_{month}"
    doc_ref = db.collection(_COLLECTION).document(doc_id)

    doc_ref.set({"user_id": user_id, "month": month, "value": value})

    return {"status": "ok", "message": "Drift logged successfully"}


def get_cohort_drift(user_id: str, month: str) -> Dict:
    """Return drift for the given month along with user history."""
    db = _get_db()
    # Get current month record
    doc_id = f"{user_id}_{month}"
    current_doc = db.collection(_COLLECTION).document(doc_id).get()
    drift_value = current_doc.to_dict().get("value", 0.0) if current_doc.exists else 0.0

    # Fetch user's entire drift history
    query = db.collection(_COLLECTION).where("user_id", "==", user_id).stream()
    history = [
        {"month": doc.to_dict()["month"], "value": doc.to_dict()["value"]}
        for doc in query
    ]

    return {
        "user_id": user_id,
        "month": month,
        "drift_value": drift_value,
        "history": sorted(history, key=lambda x: x["month"]),
    }
