"""
ReceiptCategorizationService: Enhanced service for categorizing receipt information into expense categories.
Supports multiple languages and merchant databases.
"""


class ReceiptCategorizationService:
    """
    Enhanced service to determine expense category from receipt OCR data.
    Supports Bulgarian and international merchants.
    """

    def __init__(self):
        # Enhanced keyword-based mapping with Bulgarian merchants
        self.category_keywords = {
            "groceries": [
                # International chains
                "walmart", "costco", "aldi", "whole foods", "kroger", "safeway",
                "trader joe", "target", "grocery", "supermarket", "market",
                # Bulgarian chains
                "kaufland", "lidl", "billa", "fantastico", "metro", "carrefour",
                "t market", "piccadilly", "marketplace", "магазин", "хранителен",
            ],
            "transport": [
                # Ride sharing
                "uber", "lyft", "bolt", "taxi", "cab",
                # Gas stations
                "shell", "chevron", "bp", "exxon", "mobil", "gas", "petrol", "lukoil",
                "omv", "eko", "rompetrol",
                # Public transport
                "metro", "subway", "bus", "parking", "toll",
            ],
            "entertainment": [
                "cinema", "movie", "netflix", "spotify", "amc", "theater", "theatre",
                "concert", "ticket", "entertainment", "game", "gaming", "steam",
                "кино", "театър",
            ],
            "restaurants": [
                "mcdonalds", "mcdonald's", "starbucks", "restaurant", "cafe", "coffee",
                "burger king", "kfc", "subway", "pizza", "domino", "dunkin",
                "ресторант", "кафе", "заведение", "бар",
            ],
            "shopping": [
                "amazon", "ebay", "target", "best buy", "mall", "clothing", "fashion",
                "nike", "adidas", "zara", "h&m", "store", "shop", "boutique",
                "magazine", "outlet",
            ],
            "healthcare": [
                "pharmacy", "walgreens", "cvs", "hospital", "clinic", "medical",
                "doctor", "dentist", "health", "аптека", "болница", "лекар",
                "софарма", "pharmacy",
            ],
            "utilities": [
                "electric", "electricity", "water", "gas", "utility", "bill",
                "евн", "топлофикация", "софийска вода",
            ],
            "subscriptions": [
                "subscription", "netflix", "spotify", "amazon prime", "disney",
                "youtube premium", "apple music", "hbo", "абонамент",
            ],
        }

        # Item keywords for better categorization
        self.item_keywords = {
            "groceries": [
                "bread", "milk", "cheese", "egg", "meat", "chicken", "fish",
                "vegetable", "fruit", "beer", "wine", "хляб", "мляко", "сирене",
            ],
            "restaurants": [
                "burger", "pizza", "sandwich", "drink", "coffee", "tea", "meal",
                "menu", "бургер", "пица", "сандвич",
            ],
            "healthcare": [
                "medicine", "pill", "tablet", "prescription", "лекарство", "медикамент",
            ],
        }

        self.default_category = "other"

    def categorize(
        self,
        merchant: str = "",
        amount: float = 0.0,
        items: list = None,
        hint: str = ""
    ) -> str:
        """
        Enhanced categorization based on multiple factors.

        Args:
            merchant: Merchant/store name
            amount: Transaction amount (for heuristics)
            items: List of items purchased
            hint: Category hint from OCR parser

        Returns:
            str: Detected category.
        """
        if items is None:
            items = []

        merchant_lower = merchant.lower()
        hint_lower = hint.lower()

        # Score each category
        category_scores = {}

        # 1. Check merchant name (highest priority)
        for category, keywords in self.category_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in merchant_lower:
                    score += 3  # High weight for merchant match
                    break
            category_scores[category] = score

        # 2. Check hint
        for category, keywords in self.category_keywords.items():
            for keyword in keywords:
                if keyword in hint_lower:
                    category_scores[category] = category_scores.get(category, 0) + 1
                    break

        # 3. Check items (if available)
        if items:
            for category, keywords in self.item_keywords.items():
                for item in items:
                    item_name = str(item.get("name", "")).lower()
                    for keyword in keywords:
                        if keyword in item_name:
                            category_scores[category] = category_scores.get(category, 0) + 0.5
                            break

        # 4. Amount-based heuristics
        if amount > 0:
            if amount < 10:
                # Small amounts often from cafes/transport
                category_scores["restaurants"] = category_scores.get("restaurants", 0) + 0.3
                category_scores["transport"] = category_scores.get("transport", 0) + 0.2
            elif 10 <= amount < 100:
                # Medium amounts often groceries/restaurants
                category_scores["groceries"] = category_scores.get("groceries", 0) + 0.2
                category_scores["restaurants"] = category_scores.get("restaurants", 0) + 0.2

        # Find category with highest score
        if category_scores:
            best_category = max(category_scores.items(), key=lambda x: x[1])
            if best_category[1] > 0:
                return best_category[0]

        return self.default_category

    def categorize_old_format(self, receipt_data: dict) -> str:
        """
        Legacy method for backward compatibility.

        Args:
            receipt_data: Dictionary with 'store', 'amount', 'items', 'category_hint'

        Returns:
            str: Detected category
        """
        return self.categorize(
            merchant=receipt_data.get("store", receipt_data.get("merchant", "")),
            amount=receipt_data.get("amount", receipt_data.get("total", 0.0)),
            items=receipt_data.get("items", []),
            hint=receipt_data.get("category_hint", receipt_data.get("category", ""))
        )
