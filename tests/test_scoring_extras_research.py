import pytest

from src.scoring_extras_research import (
    bowler_conceded,
    bowler_credit_wickets,
    delivery_components,
    innings_wickets,
    legal_delivery,
)


def delivery(batter=0, extras=None, total=None, wickets=None):
    extras = extras or {}
    extra_sum = sum(extras.values())
    return {
        "runs": {"batter": batter, "extras": extra_sum, "total": batter + extra_sum if total is None else total},
        "extras": extras,
        "wickets": wickets or [],
    }


def test_runs_decompose_and_typed_extras_sum():
    parts = delivery_components(delivery(batter=4, extras={"wides": 1}))
    assert parts["decomposition_ok"] is True
    assert parts["typed_extras_ok"] is True
    assert parts["total_runs"] == 5


@pytest.mark.parametrize("kind", ["byes", "legbyes", "penalty"])
def test_non_bowler_extras_are_removed_from_conceded_runs(kind):
    assert bowler_conceded(delivery(batter=2, extras={kind: 3})) == 2


@pytest.mark.parametrize("kind", ["wides", "noballs"])
def test_wides_and_no_balls_are_bowler_charged_and_illegal(kind):
    d = delivery(batter=1, extras={kind: 1})
    assert bowler_conceded(d) == 2
    assert legal_delivery(d) is False


def test_byes_and_legbyes_are_legal_unless_other_illegal_event_exists():
    assert legal_delivery(delivery(extras={"byes": 1})) is True
    assert legal_delivery(delivery(extras={"legbyes": 1})) is True


def test_unknown_other_extra_does_not_guess_bowler_concession():
    assert bowler_conceded(delivery(extras={"other": 1})) is None


def test_innings_penalty_is_separate_and_innings_total_can_include_it():
    inn = {"penalty_runs": {"pre innings": 5}, "overs": [{"over": 0, "deliveries": [delivery(batter=1)]}]}
    run_sum = sum(d["runs"]["total"] for over in inn["overs"] for d in over["deliveries"])
    penalty = sum(inn["penalty_runs"].values())
    assert run_sum + penalty == 6
    assert bowler_conceded(inn["overs"][0]["deliveries"][0]) == 1


def test_retired_hurt_retired_out_and_ordinary_wicket_semantics():
    inn = {"overs": [{"deliveries": [
        delivery(wickets=[{"kind": "retired hurt"}]),
        delivery(wickets=[{"kind": "retired out"}]),
        delivery(wickets=[{"kind": "bowled"}]),
        delivery(wickets=[{"kind": "run out"}]),
    ]}]}
    assert innings_wickets(inn) == 3
    assert bowler_credit_wickets(inn) == 1


def test_no_ball_suppresses_bowler_credit_but_team_wicket_remains():
    inn = {"overs": [{"deliveries": [delivery(extras={"noballs": 1}, wickets=[{"kind": "bowled"}])]}]}
    assert innings_wickets(inn) == 1
    assert bowler_credit_wickets(inn) == 0
