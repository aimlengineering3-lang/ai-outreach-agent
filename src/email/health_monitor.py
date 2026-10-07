"""
Computes real-time available sending capacity for a sender account —
never a hardcoded number. Also determines account health status.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from src.db.models import SenderAccount, EmailEvent


BOUNCE_RATE_THROTTLE_THRESHOLD = 0.10   # 10% bounce rate -> throttle
BOUNCE_RATE_PAUSE_THRESHOLD = 0.20      # 20% -> pause entirely
COMPLAINT_PAUSE_THRESHOLD = 3           # 3+ spam complaints in 7d -> pause


@dataclass
class CapacityResult:
    available_capacity: int
    recommended_status: str  # ACTIVE / THROTTLED / PAUSED
    reason: str


def compute_capacity(session, account: SenderAccount) -> CapacityResult:
    """
    Dynamically computes how many more emails this account can safely
    send today, factoring in provider daily_limit, sends already made,
    and recent health signals. This is the enforcement point for the
    "no hardcoded 500/1000" requirement.

    `session` is needed to look up this account's actual send volume
    over the last 7 days, so the bounce rate is computed against the
    real 7-day window instead of being skewed by how few emails have
    gone out today specifically.
    """
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date()
    if account.last_reset_at.date() != today:
        account.sent_today = 0
        account.last_reset_at = datetime.now(timezone.utc)
    if account.spam_complaint_count_7d >= COMPLAINT_PAUSE_THRESHOLD:
        return CapacityResult(0, "PAUSED", "spam_complaints_exceeded_threshold")

    remaining_by_limit = max(0, account.daily_limit - account.sent_today)

    if remaining_by_limit == 0:
        return CapacityResult(0, account.status, "daily_limit_reached")

    # Bounce rate must be computed against actual sends in the same
    # 7-day window as bounce_count_7d — dividing by sent_today alone
    # was wrong: early in the day sent_today is tiny (or 0), so a
    # handful of bounces from the last week looked like a 300-500%
    # bounce rate and falsely PAUSED healthy accounts.
    window_start = datetime.now(timezone.utc) - timedelta(days=7)
    sent_7d = (
        session.query(EmailEvent)
        .filter(
            EmailEvent.sender_account_id == account.id,
            EmailEvent.event_type.in_(["SENT", "FOLLOWUP1", "FOLLOWUP2"]),
            EmailEvent.sent_at >= window_start,
        )
        .count()
    )
    # A fresh account with no 7-day send history yet has no bounce
    # data to judge it by.
    if sent_7d > 0:
        bounce_rate = account.bounce_count_7d / sent_7d
        if bounce_rate >= BOUNCE_RATE_PAUSE_THRESHOLD:
            return CapacityResult(0, "PAUSED", "bounce_rate_critical")
        if bounce_rate >= BOUNCE_RATE_THROTTLE_THRESHOLD:
            throttled = max(0, remaining_by_limit // 2)
            return CapacityResult(throttled, "THROTTLED", "bounce_rate_elevated")

    return CapacityResult(remaining_by_limit, "ACTIVE", "healthy")


if __name__ == "__main__":
    from src.db.session import SessionLocal, init_db

    init_db()
    _session = SessionLocal()
    for _acc in _session.query(SenderAccount).all():
        print(_acc.email, "->", compute_capacity(_session, _acc))
    _session.close()