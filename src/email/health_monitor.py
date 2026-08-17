"""
Computes real-time available sending capacity for a sender account —
never a hardcoded number. Also determines account health status.
"""

from dataclasses import dataclass

from src.db.models import SenderAccount


BOUNCE_RATE_THROTTLE_THRESHOLD = 0.05   # 5% bounce rate -> throttle
BOUNCE_RATE_PAUSE_THRESHOLD = 0.10      # 10% -> pause entirely
COMPLAINT_PAUSE_THRESHOLD = 3           # 3+ spam complaints in 7d -> pause


@dataclass
class CapacityResult:
    available_capacity: int
    recommended_status: str  # ACTIVE / THROTTLED / PAUSED
    reason: str


def compute_capacity(account: SenderAccount) -> CapacityResult:
    """
    Dynamically computes how many more emails this account can safely
    send today, factoring in provider daily_limit, sends already made,
    and recent health signals. This is the enforcement point for the
    "no hardcoded 500/1000" requirement.
    """
    if account.spam_complaint_count_7d >= COMPLAINT_PAUSE_THRESHOLD:
        return CapacityResult(0, "PAUSED", "spam_complaints_exceeded_threshold")

    remaining_by_limit = max(0, account.daily_limit - account.sent_today)

    if remaining_by_limit == 0:
        return CapacityResult(0, account.status, "daily_limit_reached")

    # Bounce rate is computed against what's been sent, not the limit —
    # a fresh account with 0 sends has no bounce data yet.
    if account.sent_today > 0:
        bounce_rate = account.bounce_count_7d / max(account.sent_today, 1)
        if bounce_rate >= BOUNCE_RATE_PAUSE_THRESHOLD:
            return CapacityResult(0, "PAUSED", "bounce_rate_critical")
        if bounce_rate >= BOUNCE_RATE_THROTTLE_THRESHOLD:
            throttled = max(0, remaining_by_limit // 2)
            return CapacityResult(throttled, "THROTTLED", "bounce_rate_elevated")

    return CapacityResult(remaining_by_limit, "ACTIVE", "healthy")


if __name__ == "__main__":
    healthy_account = SenderAccount(
        email="test@gmail.com", provider="gmail", daily_limit=50,
        sent_today=10, bounce_count_7d=0, spam_complaint_count_7d=0,
    )
    print("Healthy account:", compute_capacity(healthy_account))

    unhealthy_account = SenderAccount(
        email="test2@gmail.com", provider="gmail", daily_limit=50,
        sent_today=20, bounce_count_7d=3, spam_complaint_count_7d=0,
    )
    print("Elevated bounce rate:", compute_capacity(unhealthy_account))