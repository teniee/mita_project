"""
Confidence scoring for OCR results.
Calculates confidence levels for each extracted field based on various heuristics.
"""

import re
from datetime import datetime
from typing import Dict, Any


class ConfidenceScorer:
    """Calculate confidence scores for OCR extracted data."""

    @staticmethod
    def calculate_merchant_confidence(merchant: str, raw_text: str) -> float:
        """
        Calculate confidence for merchant/store name.

        Args:
            merchant: Extracted merchant name
            raw_text: Raw OCR text

        Returns:
            Confidence score (0.0 - 1.0)
        """
        if not merchant or merchant.lower() in ["unknown", "unknown store", ""]:
            return 0.0

        confidence = 0.5  # Base confidence

        # Check if merchant appears in first few lines (likely to be correct)
        lines = raw_text.split('\n')[:3]
        if any(merchant.lower() in line.lower() for line in lines):
            confidence += 0.3

        # Check length (very short names are less reliable)
        if len(merchant) >= 3:
            confidence += 0.1
        if len(merchant) >= 5:
            confidence += 0.1

        return min(confidence, 1.0)

    @staticmethod
    def calculate_amount_confidence(amount: float, items: list, raw_text: str) -> float:
        """
        Calculate confidence for total amount.

        Args:
            amount: Extracted amount
            items: List of extracted items with prices
            raw_text: Raw OCR text

        Returns:
            Confidence score (0.0 - 1.0)
        """
        if amount <= 0:
            return 0.0

        confidence = 0.4  # Base confidence

        # Check if amount appears near "total" keyword
        total_pattern = rf"total[:\s]*\$?\s*{amount:.2f}"
        if re.search(total_pattern, raw_text.lower()):
            confidence += 0.4

        # Check if amount matches sum of items
        if items:
            items_total = sum(item.get("price", 0.0) for item in items)
            if abs(items_total - amount) < 0.01:  # Within 1 cent
                confidence += 0.3
            elif abs(items_total - amount) < amount * 0.1:  # Within 10%
                confidence += 0.15

        # Reasonable amount range (not too small or too large)
        if 0.01 <= amount <= 10000:
            confidence += 0.1

        return min(confidence, 1.0)

    @staticmethod
    def calculate_date_confidence(date_str: str, raw_text: str) -> float:
        """
        Calculate confidence for transaction date.

        Args:
            date_str: Extracted date string
            raw_text: Raw OCR text

        Returns:
            Confidence score (0.0 - 1.0)
        """
        if not date_str:
            return 0.0

        confidence = 0.3  # Base confidence

        # Try to parse the date
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d")

            # Check if date is reasonable (not in future, not too old)
            today = datetime.today()
            days_diff = (today - parsed_date).days

            if 0 <= days_diff <= 365:  # Within last year
                confidence += 0.4
            elif days_diff < 0:  # Future date (suspicious)
                confidence -= 0.2
            elif days_diff > 365 * 5:  # More than 5 years old (suspicious)
                confidence -= 0.1

            # Check if date pattern exists in raw text
            date_patterns = [
                r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',
                r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',
                r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}'
            ]
            if any(re.search(pattern, raw_text.lower()) for pattern in date_patterns):
                confidence += 0.3

        except (ValueError, TypeError):
            confidence = 0.2  # Low confidence for unparseable dates

        return max(0.0, min(confidence, 1.0))

    @staticmethod
    def calculate_category_confidence(category: str, merchant: str, items: list) -> float:
        """
        Calculate confidence for category classification.

        Args:
            category: Extracted category
            merchant: Merchant name
            items: List of items

        Returns:
            Confidence score (0.0 - 1.0)
        """
        if not category or category == "other":
            return 0.3  # Low confidence for "other" category

        confidence = 0.5  # Base confidence

        # Known merchants increase confidence
        from app.ocr.ocr_parser import CATEGORY_KEYWORDS

        if category in CATEGORY_KEYWORDS:
            merchant_lower = merchant.lower()
            keywords = CATEGORY_KEYWORDS[category]

            if any(keyword in merchant_lower for keyword in keywords):
                confidence += 0.3

        # Items consistency check
        if items and len(items) > 0:
            confidence += 0.1
            if len(items) >= 3:
                confidence += 0.1

        return min(confidence, 1.0)

    @staticmethod
    def calculate_items_confidence(items: list, amount: float) -> float:
        """
        Calculate confidence for extracted items list.

        Args:
            items: List of extracted items
            amount: Total amount

        Returns:
            Confidence score (0.0 - 1.0)
        """
        if not items:
            return 0.0

        confidence = 0.4  # Base confidence

        # Check if items have valid structure
        valid_items = [
            item for item in items
            if item.get("name") and item.get("price", 0) > 0
        ]

        if valid_items:
            confidence += 0.2

        # Check if items sum matches total
        if amount > 0:
            items_total = sum(item.get("price", 0.0) for item in items)
            diff_percentage = abs(items_total - amount) / amount if amount > 0 else 1.0

            if diff_percentage < 0.01:  # Less than 1% difference
                confidence += 0.3
            elif diff_percentage < 0.1:  # Less than 10% difference
                confidence += 0.15

        # More items generally means better extraction
        if len(valid_items) >= 3:
            confidence += 0.1

        return min(confidence, 1.0)

    @staticmethod
    def calculate_overall_confidence(
        merchant_conf: float,
        amount_conf: float,
        date_conf: float,
        category_conf: float,
        items_conf: float
    ) -> float:
        """
        Calculate overall confidence score.

        Args:
            merchant_conf: Merchant confidence
            amount_conf: Amount confidence
            date_conf: Date confidence
            category_conf: Category confidence
            items_conf: Items confidence

        Returns:
            Overall confidence score (0.0 - 1.0)
        """
        # Weighted average (amount and merchant are most important)
        weights = {
            'merchant': 0.25,
            'amount': 0.30,
            'date': 0.20,
            'category': 0.15,
            'items': 0.10
        }

        overall = (
            merchant_conf * weights['merchant'] +
            amount_conf * weights['amount'] +
            date_conf * weights['date'] +
            category_conf * weights['category'] +
            items_conf * weights['items']
        )

        return round(overall, 2)

    @classmethod
    def score_ocr_result(cls, result: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
        """
        Score all fields in OCR result and add confidence scores.

        Args:
            result: OCR result dictionary
            raw_text: Raw OCR text

        Returns:
            Result dictionary with added confidence scores
        """
        merchant = result.get("store", result.get("merchant", ""))
        amount = result.get("amount", result.get("total", 0.0))
        date = result.get("date", "")
        category = result.get("category_hint", result.get("category", ""))
        items = result.get("items", [])

        # Calculate individual confidence scores
        merchant_conf = cls.calculate_merchant_confidence(merchant, raw_text)
        amount_conf = cls.calculate_amount_confidence(amount, items, raw_text)
        date_conf = cls.calculate_date_confidence(date, raw_text)
        category_conf = cls.calculate_category_confidence(category, merchant, items)
        items_conf = cls.calculate_items_confidence(items, amount)
        overall_conf = cls.calculate_overall_confidence(
            merchant_conf, amount_conf, date_conf, category_conf, items_conf
        )

        # Add confidence scores to result
        result["confidence"] = overall_conf
        result["confidence_scores"] = {
            "merchant": round(merchant_conf, 2),
            "amount": round(amount_conf, 2),
            "date": round(date_conf, 2),
            "category": round(category_conf, 2),
            "items": round(items_conf, 2),
            "overall": overall_conf
        }

        # Identify fields needing review (confidence < 0.6)
        fields_needing_review = []
        if merchant_conf < 0.6:
            fields_needing_review.append("merchant")
        if amount_conf < 0.6:
            fields_needing_review.append("amount")
        if date_conf < 0.6:
            fields_needing_review.append("date")
        if category_conf < 0.6:
            fields_needing_review.append("category")

        result["fields_needing_review"] = fields_needing_review

        return result
