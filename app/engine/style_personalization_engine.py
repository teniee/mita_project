class StylePersonalizationEngine:
    """Generate UI and tone tweaks based on user behavior profile."""

    def __init__(self) -> None:
        """Currently stateless but left for future extensibility."""
        pass

    def adapt(self, profile):
        style = profile.get("behavior", "neutral")
        if style == "spender":
            return {
                "push_tone": "urgent",
                "ui_style": "bold",
                "challenges": ["hard-save", "block impulse"],
            }
        elif style == "saver":
            return {
                "push_tone": "calm",
                "ui_style": "minimal",
                "challenges": ["optimize budget", "save more"],
            }
        else:
            return {
                "push_tone": "neutral",
                "ui_style": "standard",
                "challenges": ["baseline challenge"],
            }
