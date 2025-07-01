### assistant_personality_layer.py — assistant tone + behavior tuning

def style_response(text: str, tone: str = "default") -> str:
    if tone == "savage":
        return f"🚨 Straight up: {text}"
    elif tone == "coach":
        return f"💪 Keep going: {text}"
    elif tone == "soft":
        return f"🌱 Just a thought: {text}"
    return text
