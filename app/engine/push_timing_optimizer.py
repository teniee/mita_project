### push_timing_optimizer.py — finds best time to send push for engagement

import random
from datetime import datetime

user_push_log = {}


def log_push(user_id: str, timestamp: datetime):
    if user_id not in user_push_log:
        user_push_log[user_id] = []
    user_push_log[user_id].append(timestamp)


def get_best_push_hour(user_id: str):
    hours = [t.hour for t in user_push_log.get(user_id, [])]
    if not hours:
        return random.choice(range(9, 21))  # 9AM–8PM
    return max(set(hours), key=hours.count)
