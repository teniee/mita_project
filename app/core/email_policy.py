"""E-mail address acceptance shared by the API and the MCP service.

``standardized_error_handler.validate_email`` (mobile registration) and the
ChatGPT sign-up page accept exactly the same addresses, normalized the same
way, so one person cannot end up with two accounts that differ only in case
or surrounding whitespace.
"""

import re
from typing import Optional

EMAIL_PATTERN = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
MAX_EMAIL_LENGTH = 254  # RFC 5321

_EMAIL_RE = re.compile(EMAIL_PATTERN)


def normalize_email(raw: object) -> Optional[str]:
    """The canonical form of an acceptable address, or None."""
    if not isinstance(raw, str):
        return None
    email = raw.strip().lower()
    if not email or len(email) > MAX_EMAIL_LENGTH or not _EMAIL_RE.match(email):
        return None
    return email
