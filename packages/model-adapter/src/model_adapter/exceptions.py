"""Custom exception types for model_adapter.

These wrap underlying AWS / boto3 errors so callers see an actionable IAM
diagnostic instead of a generic ClientError stack trace.
"""

from __future__ import annotations


class BedrockAccessDenied(Exception):
    """Raised when Bedrock returns AccessDeniedException for an InvokeModel call.

    The message always names the attempted model ARN and the
    `bedrock:InvokeModel` IAM action so the user can fix permissions without
    a CloudTrail hunt.
    """


class GatewayAccessDenied(Exception):
    """Raised when the Vercel AI Gateway rejects a request for auth reasons.

    Covers two cases, both surfaced with an actionable message:
      - The `AI_GATEWAY_API_KEY` environment variable is unset when a
        `backend = "vercel"` role is built (preflight config error).
      - The gateway returns 401 / `openai.AuthenticationError` on invoke.

    The message always names `AI_GATEWAY_API_KEY` and the gateway base URL so
    the user can fix credentials without a server-log hunt. Mirrors
    `BedrockAccessDenied` for the Bedrock path.
    """
