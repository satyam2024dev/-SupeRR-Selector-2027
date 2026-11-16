from src.ipl_2027_availability import build_availability


def test_availability_overlay_keeps_all_eligible_batters_and_no_bowler_recommendations():
    data = build_availability()
    batters = data.loc[data.candidate_role.eq("batter")]
    bowlers = data.loc[data.candidate_role.eq("bowler")]
    assert len(batters) == 107
    assert batters.performance_eligible.all()
    assert len(bowlers) == 145
    assert not bowlers.performance_eligible.any()
    assert not data.duplicated(["player_id", "candidate_role"]).any()
    assert data.source_url.notna().all()
    assert data.verification_date.eq("2026-11-13").all()


def test_official_trades_are_marked_but_never_as_auction_available():
    data = build_availability()
    traded = data.loc[data.ipl_2027_status.eq("traded_to_other_franchise")]
    assert set(traded.player_id.astype(str)) == {"4391", "4816", "7920", "4703", "3644", "4265"}
    assert traded.source_url.str.startswith("https://www.iplt20.com/news/article/").all()
    assert not traded.ipl_2027_status.isin({"officially_registered_for_auction", "included_in_final_auction_register"}).any()
    assert data.ipl_2027_status.eq("included_in_final_auction_register").sum() == 0
