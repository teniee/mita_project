"""Shared tool metadata."""

from __future__ import annotations

from typing import Any, Dict

from mcp_types import ToolAnnotations

# Stated on every tool: a fact about MITA, not an instruction about any other
# service (OpenAI forbids metadata that steers the model elsewhere).
NO_MONEY_MOVEMENT = (
    "MITA cannot initiate, execute or facilitate payments or money transfers."
)

READ_ONLY_DISCLAIMER = (
    "Read-only: this tool cannot create, change or delete anything, and MITA cannot "
    "initiate, execute or facilitate payments or money transfers."
)


def read_only_annotations(title: str) -> ToolAnnotations:
    """Reads (or computes from) the signed-in user's own MITA data, nothing else."""
    return ToolAnnotations(
        title=title,
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    )


def write_annotations(
    title: str, *, destructive: bool, idempotent: bool
) -> ToolAnnotations:
    """Changes the signed-in user's own MITA data, nothing outside it.

    ``destructive``: the tool may delete or overwrite data the user already has
    (OpenAI: the host then asks for explicit approval). ``idempotent``: calling
    it again with the same arguments has no further effect — for create tools
    that is only true because the arguments include an idempotency key.
    """
    return ToolAnnotations(
        title=title,
        read_only_hint=False,
        destructive_hint=destructive,
        idempotent_hint=idempotent,
        open_world_hint=False,
    )


def tool_meta(scope: str, invoking: str, invoked: str, **extra: Any) -> Dict[str, Any]:
    return {
        "securitySchemes": [{"type": "oauth2", "scopes": [scope]}],
        "openai/toolInvocation/invoking": invoking,
        "openai/toolInvocation/invoked": invoked,
        **extra,
    }
