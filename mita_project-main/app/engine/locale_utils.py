from babel.numbers import format_currency as babel_format_currency

def format_currency(amount: float, currency: str = "USD", locale: str = "en_US") -> str:
    try:
        return babel_format_currency(amount, currency, locale=locale)
    except Exception:
        # Fallback to basic format
        return f"{amount:.2f} {currency}"
