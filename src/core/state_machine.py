"""
Deterministic state transitions for a Lead's outreach lifecycle.

Why no LLM here: state transitions are compliance-critical (e.g. "did
this lead unsubscribe, so must never be contacted again"). An LLM
making this decision would be non-deterministic and non-auditable —
unacceptable for a rule that has legal/ethical weight. Every transition
here is a plain if/else against known, logged facts.
"""

from enum import Enum


class LeadStatus(str, Enum):
    NEW = "NEW"
    RESEARCHED = "RESEARCHED"
    QUEUED = "QUEUED"
    CONTACTED = "CONTACTED"
    FOLLOWUP_1 = "FOLLOWUP_1"
    FOLLOWUP_2 = "FOLLOWUP_2"
    REPLIED = "REPLIED"
    STOPPED = "STOPPED"
    NO_REPLY = "NO_REPLY"
    BOUNCED = "BOUNCED"
    SUPPRESSED = "SUPPRESSED"
    COMPLETED = "COMPLETED"


# Explicit allow-list of valid transitions. Any transition not listed
# here is rejected — this prevents bugs where a status accidentally
# skips a required step (e.g. NEW jumping straight to CONTACTED without
# being researched first).
ALLOWED_TRANSITIONS: dict[LeadStatus, set[LeadStatus]] = {
    LeadStatus.NEW: {LeadStatus.RESEARCHED},
    LeadStatus.RESEARCHED: {LeadStatus.QUEUED},
    LeadStatus.QUEUED: {LeadStatus.CONTACTED, LeadStatus.SUPPRESSED},
    LeadStatus.CONTACTED: {
        LeadStatus.REPLIED, LeadStatus.NO_REPLY, LeadStatus.BOUNCED, LeadStatus.SUPPRESSED,
    },
    LeadStatus.NO_REPLY: {
        LeadStatus.COMPLETED, LeadStatus.REPLIED, LeadStatus.SUPPRESSED,
    },
    LeadStatus.FOLLOWUP_1: {
        LeadStatus.REPLIED, LeadStatus.NO_REPLY, LeadStatus.BOUNCED, LeadStatus.SUPPRESSED,
    },
    LeadStatus.FOLLOWUP_2: {
        LeadStatus.REPLIED, LeadStatus.COMPLETED, LeadStatus.BOUNCED, LeadStatus.SUPPRESSED,
    },
    LeadStatus.REPLIED: {LeadStatus.STOPPED},
    LeadStatus.COMPLETED: {LeadStatus.NEW},  # only after 90-day cooldown, enforced by caller
    # STOPPED, BOUNCED, SUPPRESSED are terminal from this machine's
    # perspective (SUPPRESSED permanence itself is enforced in suppression.py)
}


class InvalidTransitionError(Exception):
    pass


def transition(current: LeadStatus, target: LeadStatus) -> LeadStatus:
    """
    Validates and returns the new status. Raises if the transition isn't
    in the allow-list — callers must fix their logic, not silently coerce
    an invalid transition into happening.
    """
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTransitionError(
            f"Cannot transition from {current.value} to {target.value}. "
            f"Allowed: {[s.value for s in allowed]}"
        )
    return target


if __name__ == "__main__":
    status = LeadStatus.NEW
    status = transition(status, LeadStatus.RESEARCHED)
    print("New status:", status)

    try:
        transition(LeadStatus.NEW, LeadStatus.CONTACTED)  # should fail
    except InvalidTransitionError as e:
        print("Correctly rejected invalid transition:", e)