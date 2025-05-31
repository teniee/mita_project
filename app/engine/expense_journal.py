from typing import Dict, List
from datetime import datetime

class ExpenseJournal:
    def __init__(self):
        self.log: Dict[str, List[dict]] = {}

    def add_entry(self, user_id: str, action: str, payload: dict):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "data": payload
        }
        self.log.setdefault(user_id, []).append(entry)

    def get_history(self, user_id: str) -> List[dict]:
        return self.log.get(user_id, [])

    def filter_by_action(self, user_id: str, action: str) -> List[dict]:
        return [e for e in self.get_history(user_id) if e["action"] == action]

    def get_last(self, user_id: str) -> dict:
        return self.log.get(user_id, [])[-1] if self.log.get(user_id) else None