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
