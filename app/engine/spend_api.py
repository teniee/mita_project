from mita_calendar.budget_tracker import get_limit, get_spent
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def category_spend_summary(request):
    calendar_id = request.query_params.get("calendar_id")
    category = request.query_params.get("category")

    if not calendar_id or not category:
        return Response({"error": "Missing calendar_id or category"}, status=400)

    spent = get_spent(calendar_id, category)
    limit = get_limit(calendar_id, category)
    return Response(
        {
            "calendar_id": calendar_id,
            "category": category,
            "spent": spent,
            "limit": limit,
        }
    )
