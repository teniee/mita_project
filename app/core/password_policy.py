"""The MITA user password policy, without framework dependencies.

``SecurityUtils.validate_password_strength`` (API) and the ChatGPT sign-up
page (MCP service, which does not install fastapi) both enforce this one
rule set, so a password accepted in one place is accepted in the other.
"""

from typing import Optional

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


def password_policy_violation(password: Optional[str]) -> Optional[str]:
    """The first rule ``password`` breaks, as a user-facing message, or None."""
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters long"
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Password cannot exceed {MAX_PASSWORD_LENGTH} characters"
    if not any(c.islower() for c in password):
        return "Password must contain lowercase letters"
    if not any(c.isupper() for c in password):
        return "Password must contain uppercase letters"
    if not any(c.isdigit() for c in password):
        return "Password must contain numbers"
    if not any(not c.isalnum() for c in password):
        return "Password must contain special characters"
    return None
