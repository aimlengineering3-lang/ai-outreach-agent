"""
Computes real-time available sending capacity for a sender account —
never a hardcoded number. Also determines account health status.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from src.db.models import SenderAccount, EmailEvent


BOUNCE_RATE_THROTTLE_THRESHOLD = 0.05   # 5% bounce rate -> throttle
BOUNCE_RATE_PAUSE_THRESHOLD =0.10      # 10% -> pause entirely
COMPLAINT_PAUSE_THRESHOLD = 3           # 3+ spam complaints in 7d -> 
MIN_SAMPLE_SIZE = 50  # 7-day volume neeche ho to bounce rate statistically unreliable hai


@dataclass
class CapacityResult:
    available_capacity: int
    recommended_status: str  # ACTIVE / THROTTLED / PAUSED
    reason: str
    bounce_window_days: int = 7  # 7 ya 30 — jo window asal me bounce rate ke liye use hui


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
        return CapacityResult(0, "PAUSED", "spam_complaints_exceeded_threshold", 7)

    remaining_by_limit = max(0, account.daily_limit - account.sent_today)

    if remaining_by_limit == 0:
        return CapacityResult(0, account.status, "daily_limit_reached", 7)

    # Bounce rate must be computed against actual sends in the same
    # 7-day window as bounce_count_7d — dividing by sent_today alone
    # was wrong: early in the day sent_today is tiny (or 0), so a
    # handful of bounces from the last week looked like a 300-500%
    # bounce rate and falsely PAUSED healthy accounts.
    window_start = datetime.now(timezone.utc) - timedelta(days=7)

    # Count bounces from the real events inside the same 7-day window as
    # the sends, instead of trusting a running total that never expires.
    def counts(since):
        bounces = (
            session.query(EmailEvent)
            .filter(
                EmailEvent.sender_account_id == account.id,
                EmailEvent.event_type == "BOUNCE",
                EmailEvent.sent_at >= since,
            )
            .count()
        )
        sends = (
            session.query(EmailEvent)
            .filter(
                EmailEvent.sender_account_id == account.id,
                EmailEvent.event_type.in_(["SENT", "FOLLOWUP1", "FOLLOWUP2"]),
                EmailEvent.sent_at >= since,
            )
            .count()
        )
        return bounces, sends

    bounces_7d, sent_7d = counts(window_start)
    window_days = 7

    if sent_7d < MIN_SAMPLE_SIZE:
        window_start = datetime.now(timezone.utc) - timedelta(days=30)
        bounces_7d, sent_7d = counts(window_start)
        window_days = 30

    # Keep the stored number (shown on the dashboard) equal to the real one.
    account.bounce_count_7d = bounces_7d

    if sent_7d > 0:
        bounce_rate = bounces_7d / sent_7d
        if bounce_rate >= BOUNCE_RATE_PAUSE_THRESHOLD:
            return CapacityResult(0, "PAUSED", "bounce_rate_critical", window_days)
        if bounce_rate >= BOUNCE_RATE_THROTTLE_THRESHOLD:
            # THROTTLED = din ka total sirf aadhi daily limit tak. Pehle yahan
            # 'bachi hui capacity ka aadha' tha, jo har refresh par dobara
            # aadha-aadha karke poori limit tak pahunch jata tha.
            throttled = max(0, min(remaining_by_limit, account.daily_limit // 2 - account.sent_today))
            return CapacityResult(throttled, "THROTTLED", "bounce_rate_elevated", window_days)

    return CapacityResult(remaining_by_limit, "ACTIVE", "healthy", window_days)


if __name__ == "__main__":
    from src.db.session import SessionLocal, init_db

    init_db()
    _session = SessionLocal()
    for _acc in _session.query(SenderAccount).all():
        print(_acc.email, "->", compute_capacity(_session, _acc))
    _session.close()