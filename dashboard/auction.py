"""RR auction availability and performance shortlist presentation."""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

STATUS_LABELS = {
    "retained_by_another_franchise": "Retained by another franchise  unavailable",
    "retained_by_rr": "Retained by Rajasthan Royals  already contracted",
    "released_by_another_franchise_pending_registration": "Released by another franchise  registration pending",
    "released_by_rr_pending_registration": "Released by Rajasthan Royals  registration pending",
    "traded_to_other_franchise": "Traded to another franchise  unavailable through auction",
    "officially_registered_for_auction": "Officially registered for the auction",
    "included_in_final_auction_register": "Included in final auction register",
    "unknown_unverified": "Unknown / unverified",
}
AUCTION_POOL_STATUSES = {"officially_registered_for_auction", "included_in_final_auction_register"}


@st.cache_data(show_spinner=False)
def _availability_csv(path: str, modified: float) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def _score_reason(row: pd.Series) -> str:
    rank = row.get("performance_rank_ipl")
    score = row.get("performance_score_ipl")
    pressure = row.get("pressure_sr_contextual")
    baseline = row.get("baseline_sr_contextual")
    if pd.notna(pressure) and pd.notna(baseline):
        change = float(pressure) - float(baseline)
        comparison = f"Contextual ordinary-subset SR {change:+.1f} versus paired baseline ({pressure:.1f} vs {baseline:.1f})."
    else:
        comparison = "Comparable pressure/baseline strike-rate evidence is unavailable."
    return f"Existing IPL performance rank {int(rank) if pd.notna(rank) else 'not assigned'}; score {float(score):.3f} where available. {comparison} This is contextual batting-resource evidence, not verified psychological pressure." if pd.notna(score) else f"No validated role score. {comparison}"


def render_auction_targets(root: Path, artifact, markdown) -> None:
    st.title("RR Auction Targets")
    st.caption("IPL 2027 availability overlay on the existing validated performance evidence. Status checked 13 November 2026.")
    path = root / "data" / "external" / "ipl_2027_player_availability.csv"
    if not path.is_file():
        st.error("The auditable availability dataset is missing. Run `python -m src.ipl_2027_availability` from the project root.")
        return
    try:
        availability = _availability_csv(str(path), path.stat().st_mtime)
    except Exception as exc:
        st.error(f"Could not load the availability dataset: {exc}")
        return

    st.info("As of 13 November, franchise retention/release lists are not yet due. Auction registration closes 23 November and the final register is scheduled for 3 December. No player is treated as auction-available until official registration or the final register is verified.")
    st.caption("Official auction rules: [IPL Player Regulations 202527](https://www.iplt20.com/news/article/ipl-governing-council-announces-tata-ipl-player-regulations-2025-27). Process timeline: [Cricbuzz report on BCCI dates](https://www.cricbuzz.com/cricket-news/140762/bcci-extends-ipl-retention-deadline-to-november-17-cricbuzzcom).")

    top10 = artifact("phase5g_overall_batter_top10.csv", package=True)
    unknown_batters = availability.loc[availability.candidate_role.eq("batter") & availability.performance_eligible.fillna(False)]
    auction_batters = unknown_batters.loc[unknown_batters.ipl_2027_status.isin(AUCTION_POOL_STATUSES)]
    bowling = availability.loc[availability.candidate_role.eq("bowler")]
    c = st.columns(4)
    c[0].metric("Performance Top 10", len(top10))
    c[1].metric("Eligible IPL batter profiles", len(unknown_batters))
    c[2].metric("Verified auction-pool batters", len(auction_batters))
    c[3].metric("Competition-ready bowlers", "0")

    tabs = st.tabs(["Two independent lists", "Available batter targets", "Bowler availability", "Availability audit"])
    with tabs[0]:
        st.subheader("LIST 1  Performance Top 10")
        st.caption("Frozen Phase 5G overall order. Scores and ranking methodology are displayed from the validated artifact without recalculation.")
        if top10.empty:
            st.warning("The validated Phase 5G Top 10 artifact is unavailable.")
        else:
            top_view = top10[[col for col in ["rank", "player_name", "player_id", "mean_within_format_percentile", "formats", "mean_pressure_matches", "mean_baseline_matches", "mean_exposure_shrinkage", "mean_consistency_factor"] if col in top10.columns]]
            st.dataframe(top_view, hide_index=True, width="stretch")
        st.subheader("LIST 2  IPL 2027 Auction Target Shortlist")
        if auction_batters.empty:
            st.warning("No performance-qualified batter is confirmed in the auction pool yet. The retained/released list deadline, registration close and final register are still pending; the target shortlist is therefore empty rather than filled with assumed availability.")
        else:
            st.dataframe(auction_batters.sort_values("performance_rank_ipl")[["player_name", "player_id", "performance_rank_ipl", "performance_score_ipl", "ipl_2027_status", "previous_franchise"]], hide_index=True, width="stretch")
        st.markdown("**Bowling:** no ranked target list. The project has 0 competition-ready bowlers and 414 exploratory profiles. Availability is shown separately from performance evidence.")

    with tabs[1]:
        st.subheader("Available batter targets")
        st.caption("Only officially registered players or names in the final auction register qualify as available targets. A release alone is not sufficient.")
        if auction_batters.empty:
            st.info("No confirmed available batter targets as of 13 November 2026.")
        else:
            st.dataframe(auction_batters.sort_values("performance_rank_ipl"), hide_index=True, width="stretch")
        st.subheader("Availability unconfirmed")
        statuses = sorted(unknown_batters.loc[unknown_batters.ipl_2027_status.isin({"unknown_unverified", "released_by_another_franchise_pending_registration", "released_by_rr_pending_registration"}), "ipl_2027_status"].dropna().unique().tolist())
        chosen = st.multiselect("Availability status", statuses, default=statuses, format_func=lambda x: STATUS_LABELS.get(x, x))
        filtered = unknown_batters.loc[unknown_batters.ipl_2027_status.isin(chosen)].sort_values("performance_rank_ipl")
        display_cols = ["performance_rank_ipl", "player_name", "player_id", "performance_score_ipl", "pressure_events", "pressure_matches", "baseline_events", "baseline_matches", "pressure_sr_contextual", "baseline_sr_contextual", "delta_sr_contextual", "pressure_dot_rate_contextual", "baseline_dot_rate_contextual", "match_consistency_index", "consistency_reliability_factor", "leave_one_match_top10_rate", "leave_one_season_top10_rate", "previous_franchise", "ipl_2027_status"]
        st.dataframe(filtered[[col for col in display_cols if col in filtered]], hide_index=True, width="stretch", height=420)
        if len(filtered):
            ids = filtered.player_id.astype(str).tolist()
            selected = st.selectbox("Candidate profile", ids, format_func=lambda pid: f"{filtered.loc[filtered.player_id.astype(str).eq(pid), 'player_name'].iloc[0]}  {pid}")
            profile = filtered.loc[filtered.player_id.astype(str).eq(selected)].iloc[0]
            st.markdown(f"### {profile.player_name}  ID {profile.player_id}")
            st.write(_score_reason(profile))
            if pd.notna(profile.get("pressure_dot_rate_contextual")) and pd.notna(profile.get("baseline_dot_rate_contextual")):
                st.write(f"Contextual dot rates: {profile.pressure_dot_rate_contextual:.1%} under the ranking context; {profile.baseline_dot_rate_contextual:.1%} paired baseline.")
            st.write(f"**Exposure:** {profile.pressure_events:g} pressure-context events across {profile.pressure_matches:g} matches; {profile.baseline_events:g} paired baseline events across {profile.baseline_matches:g} matches." if pd.notna(profile.pressure_events) and pd.notna(profile.baseline_events) else "Exposure detail is unavailable.")
            st.write(f"**Consistency:** match index {profile.match_consistency_index:.3f}; reliability factor {profile.consistency_reliability_factor:.3f}." if pd.notna(profile.match_consistency_index) and pd.notna(profile.consistency_reliability_factor) else "Consistency evidence unavailable.")
            st.write(f"**Stability:** leave-one-match Top 10 rate {profile.leave_one_match_top10_rate:.0%}; leave-one-season rate {profile.leave_one_season_top10_rate:.0%}." if pd.notna(profile.leave_one_match_top10_rate) and pd.notna(profile.leave_one_season_top10_rate) else f"**Stability:** {profile.rank_stability_note or 'not reported'}.")
            st.write(f"**Availability:** {STATUS_LABELS.get(profile.ipl_2027_status, profile.ipl_2027_status)}. Previous observed franchise: {profile.previous_franchise or 'not established'}.")
            st.write("**Potential squad contribution  analytical assessment:** a batter with an eligible contextual IPL performance profile could merit further role-fit review if later confirmed in the auction pool. This dataset does not establish RR squad gaps, batting position, price, or auction availability.")
            st.caption("**Limitations:** pressure context is the validated wicket/phase proxy, not a verified chase-pressure or psychological-pressure measure. Role, squad fit and availability do not replace registration confirmation.")

    with st.expander("Not available / already contracted"):
        unavailable = unknown_batters.loc[unknown_batters.ipl_2027_status.isin({"retained_by_another_franchise", "retained_by_rr", "traded_to_other_franchise"})]
        if unavailable.empty: st.info("No performance-qualified batter is currently verified as retained or traded in this candidate set.")
        else: st.dataframe(unavailable[["player_name", "player_id", "previous_franchise", "current_franchise_if_trade_verified", "ipl_2027_status", "source_url", "source_publication_date"]], hide_index=True, width="stretch")
    with st.expander("Released, registration pending"):
        pending = unknown_batters.loc[unknown_batters.ipl_2027_status.isin({"released_by_another_franchise_pending_registration", "released_by_rr_pending_registration"})]
        if pending.empty: st.info("No verified 2027 release announcement is recorded as of the verification date.")
        else: st.dataframe(pending, hide_index=True, width="stretch")
    with tabs[2]:
        st.subheader("Bowling availability and evidence")
        st.warning("0 competition-ready candidates; 414 exploratory profiles across IPL and T20I. Exploratory profiles are not ranked, recommended, or converted into a Bowler Target Top 10.")
        st.caption("This availability view does not change the bowling evidence decision. Current records cover the analyzed IPL bowling profiles only; verified trades are labeled, and all other 2027 availability remains unknown until official lists are published.")
        statuses = sorted(bowling.ipl_2027_status.dropna().unique().tolist())
        chosen = st.multiselect("Bowler availability status", statuses, default=statuses, format_func=lambda x: STATUS_LABELS.get(x, x), key="bowler_avail_status")
        view = bowling.loc[bowling.ipl_2027_status.isin(chosen)].copy()
        st.dataframe(view[[col for col in ["player_name", "player_id", "previous_franchise", "current_franchise_if_trade_verified", "ipl_2027_status", "confidence_status", "explanation"] if col in view]], hide_index=True, width="stretch", height=420)

    with tabs[3]:
        st.subheader("Auditable availability records")
        st.caption("One record per analyzed player and role. Last observed franchise is derived from the projects IPL 2026 mapping; it does not prove a 2027 contract.")
        statuses = sorted(availability.ipl_2027_status.dropna().unique().tolist())
        chosen = st.multiselect("Filter status", statuses, default=statuses, format_func=lambda x: STATUS_LABELS.get(x, x), key="audit_availability_status")
        audit = availability.loc[availability.ipl_2027_status.isin(chosen)].copy()
        st.dataframe(audit, hide_index=True, width="stretch", height=520)
        st.markdown("**Status update protocol:** update only from an IPL/BCCI or franchise announcement. A released player remains registration-pending; move to auction-pool status only when official registration or the final register is verified. Keep the announcement URL, publication date, verification date, and explanation in this CSV.")


