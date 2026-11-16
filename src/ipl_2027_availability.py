"""Build an auditable IPL 2027 availability overlay from verified project profiles.

Availability is maintained separately from performance data. The curated transactions
below are official IPL announcements verified on 2026-11-13; update this registry only
from official franchise/IPL/BCCI announcements.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-11-13"
OFFICIAL_RULES = "https://www.iplt20.com/news/article/ipl-governing-council-announces-tata-ipl-player-regulations-2025-27"
TIMELINE_URL = "https://www.cricbuzz.com/cricket-news/140762/bcci-extends-ipl-retention-deadline-to-november-17-cricbuzzcom"

# (new franchise, prior franchise, official source URL, publication date, explanation)
VERIFIED_TRANSACTIONS = {
    4391: ("Chennai Super Kings", "Sunrisers Hyderabad", "https://www.iplt20.com/news/article/csk-and-srh-agree-to-four-player-trade", "2026-11-05", "IPL announced a completed trade ahead of IPL 2027. Not available through the auction unless subsequently released and registered."),
    4816: ("Sunrisers Hyderabad", "Chennai Super Kings", "https://www.iplt20.com/news/article/csk-and-srh-agree-to-four-player-trade", "2026-11-05", "IPL announced a completed trade ahead of IPL 2027. Not available through the auction unless subsequently released and registered."),
    7920: ("Sunrisers Hyderabad", "Chennai Super Kings", "https://www.iplt20.com/news/article/csk-and-srh-agree-to-four-player-trade", "2026-11-05", "IPL announced a completed trade ahead of IPL 2027. Not available through the auction unless subsequently released and registered."),
    4703: ("Delhi Capitals", "Lucknow Super Giants", "https://www.iplt20.com/news/article/rishabh-pant-and-kuldeep-yadav-complete-high-profile-trade-between-dc-and-lsg", "2026-06-23", "IPL announced a completed trade to Delhi Capitals. Not available through the auction unless subsequently released and registered."),
    3644: ("Lucknow Super Giants", "Delhi Capitals", "https://www.iplt20.com/news/article/rishabh-pant-and-kuldeep-yadav-complete-high-profile-trade-between-dc-and-lsg", "2026-06-23", "IPL announced a completed trade to Lucknow Super Giants. Not available through the auction unless subsequently released and registered."),
    4265: ("Sunrisers Hyderabad", "Delhi Capitals", "https://www.iplt20.com/news/article/t-natarajan-returns-to-sunrisers-hyderabad-zeeshan-ansari-moves-to-delhi-capitals", "2026-10-14", "IPL announced a completed trade to Sunrisers Hyderabad. Not available through the auction unless subsequently released and registered."),
}

VALID_STATUSES = {
    "retained_by_another_franchise", "retained_by_rr",
    "released_by_another_franchise_pending_registration", "released_by_rr_pending_registration",
    "traded_to_other_franchise", "officially_registered_for_auction",
    "included_in_final_auction_register", "unknown_unverified",
}


def _latest_ipl_franchise() -> dict[int, str]:
    mapping = pd.read_csv(ROOT / "data/raw/competition_team_player_mapping.csv")
    comps = pd.read_csv(ROOT / "data/raw/competitions.csv")
    ipl = mapping.merge(comps[["comp_id", "match_format", "season"]], on="comp_id", how="inner")
    ipl = ipl.loc[ipl.match_format.astype(str).str.upper().eq("T20") & ipl.comp_name.str.contains("IPL", case=False, na=False)]
    if ipl.empty:
        return {}
    ipl["season_num"] = pd.to_numeric(ipl.season, errors="coerce")
    latest = ipl.loc[ipl.season_num.eq(ipl.season_num.max())]
    return latest.drop_duplicates("player_id", keep="last").set_index("player_id").team_name.to_dict()


def build_availability() -> pd.DataFrame:
    """Build the candidate overlay without recalculating any performance score."""
    batter = pd.read_csv(ROOT / "outputs/reports/phase5c_batter_rankings.csv", low_memory=False)
    bowler = pd.read_csv(ROOT / "outputs/reports/phase5c_bowler_rankings.csv", low_memory=False)
    batter = batter.loc[batter.format.eq("IPL") & batter.competition_ready.fillna(False)].copy()
    # Bowling records are retained for availability filtering only. All are exploratory;
    # the dashboard must never turn these rows into ranked bowling targets.
    bowler = bowler.loc[bowler.format.eq("IPL")].copy()
    batter["candidate_role"] = "batter"
    bowler["candidate_role"] = "bowler"
    batter["performance_eligible"] = True
    bowler["performance_eligible"] = bowler.competition_ready.fillna(False).astype(bool)
    source = pd.concat([batter, bowler], ignore_index=True, sort=False)
    source["player_id"] = source.player_id.astype(str)
    previous = _latest_ipl_franchise()
    output = []
    for row in source.to_dict("records"):
        player_id = str(row["player_id"])
        numeric_id = int(float(player_id))
        previous_franchise = previous.get(numeric_id, "")
        event = VERIFIED_TRANSACTIONS.get(numeric_id)
        if event:
            new_franchise, event_previous, url, published, explanation = event
            status = "traded_to_other_franchise"
            previous_franchise = event_previous or previous_franchise
            confidence = "officially_verified_trade"
            source_url = url
            source_publication_date = published
            current_franchise = new_franchise
        else:
            status = "unknown_unverified"
            confidence = "unverified_pending_official_2027_lists"
            source_url = "https://www.iplt20.com/news"
            source_publication_date = ""
            current_franchise = ""
            explanation = ("No player-specific IPL 2027 retention, release, or trade announcement was verified as of "
                           f"{AS_OF}. The retention/release deadline is November 17, 2026; auction registration closes "
                           "November 23; the final register is scheduled for December 3. Prior franchise reflects the "
                           "latest project mapping only and does not establish a 2027 contract.")
        output.append({
            "player_id": player_id,
            "player_name": row["player_name"],
            "candidate_role": row["candidate_role"],
            "performance_eligible": bool(row["performance_eligible"]),
            "performance_rank_ipl": row.get("rank"),
            "performance_score_ipl": row.get("score"),
            "pressure_events": row.get("pressure_events"),
            "pressure_matches": row.get("pressure_matches"),
            "baseline_events": row.get("baseline_events"),
            "baseline_matches": row.get("baseline_matches"),
            "pressure_sr_contextual": row.get("pressure_sr"),
            "baseline_sr_contextual": row.get("baseline_sr"),
            "delta_sr_contextual": row.get("delta_sr"),
            "pressure_dot_rate_contextual": row.get("pressure_dot_rate"),
            "baseline_dot_rate_contextual": row.get("baseline_dot_rate"),
            "match_consistency_index": row.get("match_consistency_index"),
            "consistency_reliability_factor": row.get("consistency_reliability_factor"),
            "score_uncertainty_95_low": row.get("score_uncertainty_95_low"),
            "score_uncertainty_95_high": row.get("score_uncertainty_95_high"),
            "score_uncertainty_method": row.get("score_uncertainty_method"),
            "rank_stability_note": row.get("rank_stability_note"),
            "leave_one_match_top10_rate": row.get("leave_one_match_top10_rate"),
            "leave_one_season_top10_rate": row.get("leave_one_season_top10_rate"),
            "performance_status": "competition_ready_contextual_batter" if row["candidate_role"] == "batter" else "exploratory_only_no_bowling_recommendation",
            "previous_franchise": previous_franchise,
            "previous_franchise_source": "Project competition mapping, latest analyzed IPL season (2026)" if previous_franchise else "",
            "current_franchise_if_trade_verified": current_franchise,
            "ipl_2027_status": status,
            "confidence_status": confidence,
            "source_url": source_url,
            "source_publication_date": source_publication_date,
            "status_reference_url": OFFICIAL_RULES,
            "status_reference_publication_date": "2024-09-28",
            "process_timeline_source_url": TIMELINE_URL,
            "process_timeline_publication_date": "2026-11-02",
            "verification_date": AS_OF,
            "explanation": explanation,
        })
    result = pd.DataFrame(output)
    if not result.ipl_2027_status.isin(VALID_STATUSES).all():
        raise ValueError("Availability dataset contains an unrecognized status")
    if result.duplicated(["player_id", "candidate_role"]).any():
        raise ValueError("Availability dataset contains duplicate player-role records")
    return result


def main() -> dict:
    path = ROOT / "data/external/ipl_2027_player_availability.csv"
    result = build_availability()
    result.to_csv(path, index=False)
    return {
        "output": str(path.relative_to(ROOT)),
        "records": len(result),
        "eligible_batters": int((result.candidate_role.eq("batter") & result.performance_eligible).sum()),
        "bowling_profiles_availability_only": int(result.candidate_role.eq("bowler").sum()),
        "verified_traded_player_ids": int(result.loc[result.ipl_2027_status.eq("traded_to_other_franchise"), "player_id"].nunique()),
        "auction_registered_or_final_register": int(result.ipl_2027_status.isin({"officially_registered_for_auction", "included_in_final_auction_register"}).sum()),
        "as_of": AS_OF,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(main(), indent=2))



