"""Feedback to the MITA team, and the user's usage-statistics switch."""

from __future__ import annotations

from typing import Annotated, Literal, Optional

from mcp.server.mcpserver import Context, MCPServer
from mcp_types import CallToolResult
from pydantic import Field
from sqlalchemy import delete

from app.db.models import AnalyticsIdentity, McpUserProfile, ProductFeedback
from app.mcp import analytics, idempotency
from app.mcp.auth.scopes import FEEDBACK_WRITE, PROFILE_WRITE
from app.mcp.errors import ValidationError
from app.mcp.runtime import McpRuntime
from app.mcp.schemas import FeedbackSentOut, UsageAnalyticsOut
from app.mcp.tools.common import NO_MONEY_MOVEMENT, tool_meta, write_annotations
from app.mcp.tools.inputs import IdempotencyKey

FEEDBACK_TYPES = ("feature_request", "bug_report", "confusing", "praise", "other")
FEATURE_AREAS = (
    "transactions",
    "budget",
    "history",
    "goals",
    "recurring",
    "setup",
    "other",
)

FEEDBACK_DESCRIPTION = (
    "Send the user's own feedback to the MITA team — ONLY when the user explicitly "
    "asks to send feedback, report a problem or request a feature for MITA (e.g. "
    "'Tell the MITA team that categorization is confusing'). Never turn ordinary "
    "conversation into feedback, and confirm the wording with the user before "
    "sending. The message is stored with the user's MITA account and read by the "
    "MITA team; suggest leaving out financial details unless the user wants to "
    "include them. " + NO_MONEY_MOVEMENT
)

USAGE_DESCRIPTION = (
    "Turn the user's MITA usage statistics on or off when they ask. These record "
    "which MITA features are used and whether calls succeed — never conversations, "
    "amounts, merchants or other financial details. Turning them off also deletes "
    "the usage records already linked to the user; turning them on starts a new "
    "record from now. Confirm the choice with the user first. " + NO_MONEY_MOVEMENT
)

WHAT_IS_RECORDED = (
    "Which MITA tools and features are used, when, whether they succeeded and how "
    "long they took, under a pseudonymous key — never conversations, amounts, "
    "merchants, notes or goal titles."
)


def register(server: MCPServer, runtime: McpRuntime) -> None:
    @server.tool(
        name="submit_feedback",
        title="Send feedback to the MITA team",
        description=FEEDBACK_DESCRIPTION,
        annotations=write_annotations(
            "Send feedback to the MITA team", destructive=False, idempotent=True
        ),
        meta=tool_meta(FEEDBACK_WRITE, "Sending your feedback…", "Sent your feedback"),
    )
    async def submit_feedback(
        ctx: Context,
        type: Annotated[
            Literal[FEEDBACK_TYPES],  # type: ignore[valid-type]
            Field(description="What kind of feedback the user is giving."),
        ],
        feature_area: Annotated[
            Literal[FEATURE_AREAS],  # type: ignore[valid-type]
            Field(description="Which part of MITA it is about."),
        ],
        message: Annotated[
            str,
            Field(
                min_length=1,
                max_length=2000,
                description="The feedback in the user's own words.",
            ),
        ],
        idempotency_key: IdempotencyKey,
        rating: Annotated[
            Optional[int],
            Field(
                ge=1,
                le=5,
                description="How useful MITA is to the user (1-5), only if they said.",
            ),
        ] = None,
    ) -> Annotated[CallToolResult, FeedbackSentOut]:
        async def body(session, user_ctx, call):
            text = message.strip()
            if not text:
                raise ValidationError("message must contain the user's feedback.")

            def write(s) -> FeedbackSentOut:
                claim = idempotency.claim(
                    s,
                    user_id=user_ctx.user_id,
                    operation="submit_feedback",
                    session_digest=call.session_digest,
                    key=idempotency_key,
                    request=[type, feature_area, text, rating],
                    now=call.now,
                )
                if claim.is_replay:
                    analytics.mark_replayed()
                    status = "already_sent"
                else:
                    row = ProductFeedback(
                        user_id=user_ctx.user_id,
                        type=type,
                        feature_area=feature_area,
                        message=text,
                        rating=rating,
                        status="new",
                        source="chatgpt",
                        created_at=call.now,
                    )
                    s.add(row)
                    s.flush()
                    claim.complete([row.id])
                    s.commit()
                    status = "sent"
                    analytics.emit(
                        "feedback_submitted",
                        type=type,
                        feature_area=feature_area,
                        rating=rating,
                    )
                return FeedbackSentOut(
                    status=status,
                    type=type,
                    feature_area=feature_area,
                    rating=rating,
                    notes=["Thank you — the MITA team reads every message."],
                )

            return await session.run_sync(write)

        return await runtime.execute_write(
            "submit_feedback", FEEDBACK_WRITE, body, ctx=ctx, intent=type
        )

    @server.tool(
        name="set_usage_analytics",
        title="Change MITA usage statistics",
        description=USAGE_DESCRIPTION,
        annotations=write_annotations(
            "Change MITA usage statistics", destructive=True, idempotent=True
        ),
        meta=tool_meta(PROFILE_WRITE, "Updating your setting…", "Updated your setting"),
    )
    async def set_usage_analytics(
        ctx: Context,
        enabled: Annotated[
            bool, Field(description="True to allow, false to stop and delete.")
        ],
    ) -> Annotated[CallToolResult, UsageAnalyticsOut]:
        async def body(session, user_ctx, call):
            # Events still queued for this user are written before the link is
            # deleted, so nothing linked survives an opt-out.
            await runtime.analytics.flush()

            def write(s) -> UsageAnalyticsOut:
                profile = s.get(McpUserProfile, user_ctx.user_id)
                if profile is None:
                    profile = McpUserProfile(user_id=user_ctx.user_id)
                    s.add(profile)
                changed = bool(profile.usage_analytics_enabled) != enabled
                profile.usage_analytics_enabled = enabled
                profile.usage_analytics_updated_at = call.now
                deleted = False
                if not enabled:
                    result = s.execute(
                        delete(AnalyticsIdentity).where(
                            AnalyticsIdentity.user_id == user_ctx.user_id
                        )
                    )
                    deleted = bool(result.rowcount)
                s.commit()
                analytics.override_consent(enabled)
                if enabled and changed:
                    analytics.emit("usage_analytics_enabled")
                return UsageAnalyticsOut(
                    usage_analytics_enabled=enabled,
                    linked_data_deleted=deleted,
                    what_is_recorded=WHAT_IS_RECORDED,
                )

            return await session.run_sync(write)

        return await runtime.execute_write(
            "set_usage_analytics",
            PROFILE_WRITE,
            body,
            ctx=ctx,
            intent="privacy_setting",
        )
