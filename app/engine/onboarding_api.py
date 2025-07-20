import json
import os

from rest_framework.decorators import api_view
from rest_framework.response import Response

ONBOARDING_PATH = os.path.join(os.path.dirname(__file__), "onboarding_questions.json")


@api_view(["GET"])
def get_onboarding_questions(request):
    try:
        with open(ONBOARDING_PATH, "r", encoding="utf-8") as f:
            questions = json.load(f)
        return Response({"questions": questions})
    except Exception as e:
        return Response({"error": str(e)}, status=500)
