def rank_suggestions(suggestions: dict, behavior: str) -> list:
    """
    Ranks suggestions by importance and behavior.
    Returns list of tuples: (category, suggestion, priority)
    """
    priority_map = {"saver": 2, "spender": 3, "erratic": 4, "neutral": 1}
    ranked = []

    for cat, tip in suggestions.items():
        base = 1
        if "reducing" in tip:
            base += 1
        if behavior in ["spender", "erratic"]:
            base += 1
        priority = base + priority_map.get(behavior, 1)
        ranked.append((cat, tip, priority))

    return sorted(ranked, key=lambda x: -x[2])
