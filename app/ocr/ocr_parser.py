import re
from datetime import datetime

# Simple keyword heuristics for determining the category
CATEGORY_KEYWORDS = {
    "groceries": [
        "market",
        "grocery",
        "supermarket",
        "food",
        "aldi",
        "whole foods",
    ],
    "restaurants": [
        "restaurant",
        "burger",
        "cafe",
        "mcdonald",
        "kfc",
        "pizza",
        "diner",
    ],
    "shopping": ["store", "mall", "target", "walmart", "shopping"],
    "transport": ["uber", "lyft", "taxi", "metro", "transport"],
    "entertainment": ["movie", "cinema", "netflix", "theater", "amc"],
    "health": ["pharmacy", "drug", "health", "walgreens", "cvs"],
    "subscriptions": ["spotify", "netflix", "subscription", "prime"],
}


def parse_receipt_text(text: str) -> dict:
    lines = text.lower().splitlines()
    best_amount = 0.0
    date_found = None
    category = "other"

    # 1. Amount: choose the largest value near words like "total" or "amount"
    for line in lines:
        if "total" in line or "amount" in line or re.search(r"\$\s?\d", line):
            amounts = re.findall(r"\$?\b(\d{1,5}(\.\d{1,2})?)\b", line)
            for match in amounts:
                val = float(match[0])
                if val > best_amount:
                    best_amount = val

    # 2. Date: try multiple common formats
    date_patterns = [
        r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b",  # YYYY-MM-DD
        r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b",  # MM/DD/YY or DD-MM-YYYY
        (
            r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
            r"[a-z]*\.?\s+\d{1,2},\s+\d{4}\b"
        ),
    ]
    for line in lines:
        for pattern in date_patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    parsed_date = datetime.strptime(match.group(0), "%Y-%m-%d")
                except ValueError:
                    try:
                        parsed_date = datetime.strptime(
                            match.group(0),
                            "%m/%d/%Y",
                        )
                    except ValueError:
                        try:
                            parsed_date = datetime.strptime(
                                match.group(0),
                                "%b %d, %Y",
                            )
                        except ValueError:
                            continue
                date_found = parsed_date.date()
                break
        if date_found:
            break

    # 3. Category by matching keywords
    for line in lines:
        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(word in line for word in keywords):
                category = cat
                break
        if category != "other":
            break

    return {
        "amount": round(best_amount, 2),
        "date": str(date_found or datetime.today().date()),
        "category": category,
    }


def parse_receipt_details(text: str) -> dict:
    """Parse receipt text into merchant, items, and total fields."""
    basic = parse_receipt_text(text)
    text_lines = text.splitlines()
    lines = [item.strip() for item in text_lines if item.strip()]
    merchant = lines[0][:64] if lines else "unknown"
    item_pattern = re.compile(r"(.+?)\s+(\d+[.,]\d{2})$")
    items = []
    for line in lines[1:]:
        m = item_pattern.search(line)
        if m:
            name = m.group(1).strip()[:64]
            price = float(m.group(2).replace(",", "."))
            items.append({"name": name, "price": price})
    total = sum(i["price"] for i in items) or basic["amount"]
    return {
        "merchant": merchant,
        "items": items,
        "total": round(total, 2),
        **basic,
    }
