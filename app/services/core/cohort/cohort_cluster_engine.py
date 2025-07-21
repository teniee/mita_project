from typing import Dict, List

import numpy as np
from sklearn.cluster import KMeans


class CohortClusterEngine:
    """Simple in-memory KMeans clustering for user cohorts."""

    def __init__(self, n_clusters: int = 4):
        """Create a new clustering engine."""
        self.model = KMeans(n_clusters=n_clusters, random_state=42)
        self.user_vectors: Dict[str, List[float]] = {}
        self.labels: Dict[str, int] = {}

    def _build_vector(
        self, profile: Dict, calendar: Dict, mood: Dict, challenges: Dict
    ) -> List[float]:
        """Convert raw user blobs into a numerical feature vector."""
        income = profile.get("income", 0)
        moods = len(mood)
        mood_variety = len(set(mood.values()))
        challenge_count = len(challenges)
        total_spent = sum(day["total"] for day in calendar.values())
        avg_spent = total_spent / len(calendar) if calendar else 0
        redistribs = sum(1 for d in calendar.values() if d.get("redistributed"))

        return [income, moods, mood_variety, challenge_count, avg_spent, redistribs]

    def fit(self, user_blobs: Dict[str, Dict]):
        """Fit the cluster model on a dictionary of user data blobs."""
        vectors = []
        ids = []

        for user_id, blob in user_blobs.items():
            vec = self._build_vector(
                blob["profile"], blob["calendar"], blob["moods"], blob["challenges"]
            )
            self.user_vectors[user_id] = vec
            vectors.append(vec)
            ids.append(user_id)

        X = np.array(vectors)
        self.model.fit(X)

        for i, user_id in enumerate(ids):
            self.labels[user_id] = int(self.model.labels_[i])

    def get_label(self, user_id: str) -> int:
        """Return the assigned cluster label for a user."""
        return self.labels.get(user_id, -1)

    def get_centroids(self) -> np.ndarray:
        """Return coordinates of all cluster centroids."""
        return self.model.cluster_centers_
