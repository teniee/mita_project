def detect_anomalies(calendar: dict, threshold: float = 2.5):
    import statistics

    totals = [day["total"] for day in calendar.values() if day["total"] > 0]
    if len(totals) < 5:
        return []

    mean = statistics.mean(totals)
    stdev = statistics.stdev(totals)
    upper_limit = mean + threshold * stdev

    anomalies = []
    for day_num, day_data in calendar.items():
        if day_data["total"] > upper_limit:
            anomalies.append({
                "day": day_num,
                "total": round(day_data["total"], 2),
                "threshold": round(upper_limit, 2)
            })

    return anomalies

if __name__ == "__main__":
    from calendar_engine import CalendarEngine

    engine = CalendarEngine(
        income=3000,
        fixed_expenses=[{"day": 1, "amount": 1200, "category": "rent"}],
        discretionary_categories=[
            {"category": "groceries", "amount": 500, "frequency": 4},
            {"category": "entertainment", "amount": 200, "frequency": 2}
        ]
    )
    cal = engine.generate_calendar(2025, 4)
    anomalies = detect_anomalies(cal)
    print("Аномалии:", anomalies)