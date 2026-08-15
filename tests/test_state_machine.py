import pytest
from src.core.state_machine import LeadStatus, transition, InvalidTransitionError


def test_valid_transition():
    result = transition(LeadStatus.NEW, LeadStatus.RESEARCHED)
    assert result == LeadStatus.RESEARCHED


def test_invalid_transition_raises():
    try:
        transition(LeadStatus.NEW, LeadStatus.CONTACTED)
        assert False, "Should have raised InvalidTransitionError"
    except InvalidTransitionError:
        pass


def test_replied_leads_to_stopped_only():
    result = transition(LeadStatus.REPLIED, LeadStatus.STOPPED)
    assert result == LeadStatus.STOPPED
    try:
        transition(LeadStatus.REPLIED, LeadStatus.FOLLOWUP_1)
        assert False, "Replied lead must not be able to receive followups"
    except InvalidTransitionError:
        pass


if __name__ == "__main__":
    test_valid_transition()
    test_invalid_transition_raises()
    test_replied_leads_to_stopped_only()
    print("All state_machine tests passed.")