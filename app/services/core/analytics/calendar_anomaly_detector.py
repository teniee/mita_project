from statistics import mean, stdev
from typing import Dict, List, Any

def detect_anomalies(calendar: Dict[int, Dict[str, Any]], threshold: float = 2.5) -> List[Dict[str, Any]]:
    """
    Detects spending anomalies in a calendar.
    Returns a list of days where total spending is beyond threshold * stddev from mean.
    """
    totals = [day.get("total", 0.0) for day in calendar.values() if day.get("total", 0.0) > 0]
    if len(totals) < 5:
        return []

    avg = mean(totals)
    std = stdev(totals)
    upper_limit = avg + threshold * std

    anomalies = []
    for day_num, day_data in calendar.items():
        if day_data.get("total", 0.0) > upper_limit:
            anomalies.append({
                "day": day_num,
                "total": round(day_data["total"], 2),
                "threshold": round(upper_limit, 2)
            })

    return anomalies