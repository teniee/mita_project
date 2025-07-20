### goal_mode_ui_api.py — API surface to show goal progress in UI


def get_goal_progress(state: dict) -> dict:
    saved = state.get("progress", {}).get("saved", 0)
    goal = state.get("savings_target", 0)
    if goal == 0:
        return {"error": "no goal set"}

    progress = min(1.0, saved / goal)
    remaining = round(goal - saved, 2)

    return {
        "progress_pct": round(progress * 100, 1),
        "remaining_to_goal": remaining,
        "goal": goal,
        "saved": saved,
    }
