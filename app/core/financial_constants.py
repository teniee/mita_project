"""Financial validation constants shared by the API and the MCP service.

Dependency-free on purpose: ``app.core.validators`` (which re-exports this
class) imports bleach, phonenumbers and fastapi, none of which the MCP image
installs. Both services must validate money and categories against the SAME
values, so the constants live here and nowhere else.
"""

from decimal import Decimal


# Financial application constants
class FinancialConstants:
    """Constants for financial validation in MITA application"""

    # Currency configurations
    SUPPORTED_CURRENCIES = {"USD"}  # Currently US-only, expandable for international
    DEFAULT_CURRENCY = "USD"

    # Financial limits (in USD)
    MIN_TRANSACTION_AMOUNT = Decimal("0.01")
    MAX_TRANSACTION_AMOUNT = Decimal("999999.99")
    MIN_ANNUAL_INCOME = Decimal("0.00")
    MAX_ANNUAL_INCOME = Decimal("99999999.99")
    MIN_BUDGET_AMOUNT = Decimal("0.01")
    MAX_BUDGET_AMOUNT = Decimal("9999999.99")
    MIN_GOAL_AMOUNT = Decimal("1.00")
    MAX_GOAL_AMOUNT = Decimal("99999999.99")

    # Geographic constraints (US-only for now)
    SUPPORTED_COUNTRIES = {"US"}
    US_STATES = {
        "AL",
        "AK",
        "AZ",
        "AR",
        "CA",
        "CO",
        "CT",
        "DE",
        "FL",
        "GA",
        "HI",
        "ID",
        "IL",
        "IN",
        "IA",
        "KS",
        "KY",
        "LA",
        "ME",
        "MD",
        "MA",
        "MI",
        "MN",
        "MS",
        "MO",
        "MT",
        "NE",
        "NV",
        "NH",
        "NJ",
        "NM",
        "NY",
        "NC",
        "ND",
        "OH",
        "OK",
        "OR",
        "PA",
        "RI",
        "SC",
        "SD",
        "TN",
        "TX",
        "UT",
        "VT",
        "VA",
        "WA",
        "WV",
        "WI",
        "WY",
        "DC",
    }

    # Transaction categories for strict validation
    VALID_TRANSACTION_CATEGORIES = {
        "food",
        "dining",
        "groceries",
        "transportation",
        "gas",
        "public_transport",
        "entertainment",
        "shopping",
        "clothing",
        "healthcare",
        "insurance",
        "utilities",
        "rent",
        "mortgage",
        "education",
        "childcare",
        "pets",
        "travel",
        "subscriptions",
        "gifts",
        "charity",
        "income",
        "other",
    }

    # Goal categories
    VALID_GOAL_CATEGORIES = {
        "savings",
        "debt_payoff",
        "investment",
        "purchase",
        "travel",
        "education",
        "emergency_fund",
        "retirement",
        "healthcare",
        "other",
    }
