# app/services/core/engine/style_agent.py

from datetime import datetime
from typing import Dict


def personalize_ui(user_id: str, profile: dict) -> Dict[str, str]:
    """Return UI style settings personalized for the user.

    Args:
        user_id (str): user ID
        profile (dict): user profile (age, preferences, mood, etc.)

    Returns:
        dict: UI settings dict (theme, palette, fontSize, layout)
    """

    age = profile.get("age", 30)
    mood = profile.get("mood", "neutral")
    preferences = profile.get("preferences", {})
    preferred_theme = preferences.get("theme")
    time_now = datetime.utcnow().hour

    # Theme: light/dark
    if preferred_theme:
        theme = preferred_theme
    elif 20 <= time_now or time_now < 7:
        theme = "dark"
    else:
        theme = "light"

    # Choose palette based on mood
    if mood == "stressed":
        palette = "calm_pastel"
    elif mood == "motivated":
        palette = "vibrant_bold"
    elif mood == "sad":
        palette = "warm_soft"
    else:
        palette = "default_neutral"

    # Font size
    if age >= 55:
        font_size = "large"
    elif age <= 25:
        font_size = "normal"
    else:
        font_size = "medium"

    # Layout
    layout = preferences.get("layout", "spacious" if age > 40 else "compact")

    return {"theme": theme, "palette": palette, "fontSize": font_size, "layout": layout}
