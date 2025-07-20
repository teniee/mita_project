### anomaly_overlay.py — anomaly visual layer extractor for shell

from calendar_anomaly_detector import detect_anomalies


def get_anomaly_overlay(user_id: str, year: int, month: int):
    anomalies = detect_anomalies(user_id, year, month)
    overlay = {}
    for item in anomalies:
        day = item["day"]
        overlay[day] = {
            "category": item["category"],
            "severity": item["severity"],
            "description": item["description"],
        }
    return overlay
