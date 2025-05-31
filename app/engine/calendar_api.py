from rest_framework.decorators import api_view
from rest_framework.response import Response

from mita_calendar.calendar_engine_behavioral import build_calendar
from mita_calendar.calendar_store import save_calendar, get_calendar

@api_view(["POST"])
def generate_calendar(request):
    data = request.data
    calendar_id = data.get("calendar_id")
    start_date = data.get("start_date")
    num_days = data.get("num_days")
    budget_plan = data.get("budget_plan")

    if not all([calendar_id, start_date, num_days, budget_plan]):
        return Response({"error": "Missing required fields"}, status=400)

    try:
        calendar_days = build_calendar(start_date, int(num_days), budget_plan)
        save_calendar(calendar_id, calendar_days)
        return Response({"calendar_id": calendar_id, "days": calendar_days})
    except Exception as e:
        return Response({"error": str(e)}, status=500)

@api_view(["GET"])
def fetch_calendar(request):
    calendar_id = request.query_params.get("calendar_id")
    if not calendar_id:
        return Response({"error": "Missing calendar_id"}, status=400)

    calendar = get_calendar(calendar_id)
    return Response({"calendar_id": calendar_id, "days": calendar})