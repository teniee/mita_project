from app.engine.analysis.calendar_anomaly_detector import detect_anomalies


def test_detect_anomalies_returns_empty_for_small_sample():
    calendar = {str(i): {"total": i} for i in range(1, 4)}
    assert detect_anomalies(calendar) == []


def test_detect_anomalies_detects_outlier():
    # create 30 days mostly with small totals
    calendar = {str(i): {"total": 10} for i in range(1, 31)}
    calendar["15"]["total"] = 100
    anomalies = detect_anomalies(calendar)
    assert anomalies
    days = [a["day"] for a in anomalies]
    assert "15" in days
