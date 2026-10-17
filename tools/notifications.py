"""
Mock Customer Notification Tool for ChainSight Agent.
Generates preview messages and simulates dispatch.
Strictly labels all actions as SIMULATED.
Never sends physical external communications.
"""
from datetime import datetime, timezone
from typing import Dict, Any
from schemas import MockNotificationResult


def dispatch_mock_notification(
    recipient_segment: str,
    subject: str,
    body: str,
) -> MockNotificationResult:
    """Generate simulated customer notification record."""
    return MockNotificationResult(
        recipient_segment=recipient_segment,
        preview_subject=subject,
        preview_body=body,
        status="SIMULATED_NOT_DISPATCHED",
        timestamp=datetime.now(timezone.utc).isoformat(),
        disclaimer="Notice: This action is simulated for evaluation only. No physical message dispatched.",
    )
