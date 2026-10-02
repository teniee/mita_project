"""Shared tool metadata."""

from __future__ import annotations

from typing import Any, Dict

from mcp_types import ToolAnnotations

READ_ONLY_DISCLAIMER = (
    "Read-only: this tool cannot create, change, delete, move or pay anything."
)


def read_only_annotations(title: str) -> ToolAnnotations:
    """Every v1 tool: reads the signed-in user's own MITA data, nothing else."""
    return ToolAnnotations(
        title=title,
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    )


def tool_meta(scope: str, invoking: str, invoked: str, **extra: Any) -> Dict[str, Any]:
    return {
        "securitySchemes": [{"type": "oauth2", "scopes": [scope]}],
        "openai/toolInvocation/invoking": invoking,
        "openai/toolInvocation/invoked": invoked,
        **extra,
    }
