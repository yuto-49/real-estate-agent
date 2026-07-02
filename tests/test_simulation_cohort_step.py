from domain.reactions.models import ReactionEvent, ReactionVector
from domain.simulation.models import CohortState
from domain.simulation.cohort_step import update_cohorts


def test_shock_increases_churn():
    cohort = CohortState("1K_中央区", 50, ReactionVector(), 0.03, 0.2)
    events = (ReactionEvent(topic="rent_decline", variable="affordability_pressure", delta=0.3),)
    updated = update_cohorts((cohort,), events)
    assert updated[0].churn_probability > cohort.churn_probability


def test_no_events_minimal_change():
    cohort = CohortState("test", 10, ReactionVector(), 0.02, 0.1)
    updated = update_cohorts((cohort,), ())
    assert updated[0].churn_probability == cohort.churn_probability
