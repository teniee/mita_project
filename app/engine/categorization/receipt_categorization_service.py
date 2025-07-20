"""
ReceiptCategorizationService: Service for categorizing receipt information into expense categories.
"""


class ReceiptCategorizationService:
    """
    Service to determine expense category from receipt OCR data.
    """

    def __init__(self):
        # Simple keyword-based mapping
        self.category_keywords = {
            "groceries": [
                "walmart",
                "costco",
                "aldi",
                "whole foods",
                "grocery",
                "supermarket",
            ],
            "transport": ["uber", "lyft", "taxi", "shell", "chevron", "gas", "metro"],
            "entertainment": [
                "cinema",
                "movie",
                "netflix",
                "amc",
                "theater",
                "entertainment",
            ],
            "restaurants": [
                "mcdonalds",
                "starbucks",
                "restaurant",
                "cafe",
                "burger king",
            ],
            "shopping": ["amazon", "target", "best buy", "mall", "clothing"],
            "healthcare": ["pharmacy", "walgreens", "cvs", "hospital", "clinic"],
        }
        self.default_category = "other"

    def categorize(self, receipt_data: dict) -> str:
        """
        Categorize receipt based on store name and hints.

        Args:
            receipt_data (dict): Must contain 'store' and optionally 'category_hint'.

        Returns:
            str: Detected category.
        """
        store = receipt_data.get("store", "").lower()
        hint = receipt_data.get("category_hint", "").lower()

        # Check store name first
        for category, keywords in self.category_keywords.items():
            if any(keyword in store for keyword in keywords):
                return category

        # If store didn't match, check hint
        for category, keywords in self.category_keywords.items():
            if any(keyword in hint for keyword in keywords):
                return category

        return self.default_category
