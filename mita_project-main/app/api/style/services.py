
from app.services.core.engine.style_agent import personalize_ui

def get_ui_style(user_id: str, profile: dict) -> dict:
    return personalize_ui(user_id, profile)
