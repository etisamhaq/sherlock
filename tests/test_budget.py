import pytest

from sherlock.budget import Budget, BudgetExceeded


def test_token_budget_enforced():
    b = Budget(token_budget=1000, time_budget_seconds=1000)
    b.add_tokens(900)
    b.check()  # under budget, no raise
    b.add_tokens(200)
    with pytest.raises(BudgetExceeded):
        b.check()


def test_tokens_remaining():
    b = Budget(token_budget=1000)
    b.add_tokens(300)
    assert b.tokens_remaining() == 700


def test_time_budget_enforced_with_fake_clock():
    ticks = iter([0.0, 0.0, 5.0])  # start, then two checks

    def clock():
        return next(ticks)

    b = Budget(token_budget=10_000, time_budget_seconds=3.0, clock=clock)
    # first check at t=0 → fine; second at t=5 → exceeded
    b.check()
    with pytest.raises(BudgetExceeded):
        b.check()


def test_negative_tokens_ignored():
    b = Budget(token_budget=100)
    b.add_tokens(-50)
    assert b.tokens_spent == 0
