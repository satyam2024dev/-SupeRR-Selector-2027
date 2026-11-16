"""SupeRR Selector: cricket talent intelligence dashboard."""
from pathlib import Path
import json
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.components.ui import apply_theme, empty_data_notice, page_header, read_markdown
from dashboard.auction import render_auction_targets

REPORTS = ROOT / "outputs" / "reports"
SUBMISSION = ROOT / "submission"
NAV = ["Overview", "Player Discovery", "Batter Rankings", "Bowling Analysis", "Player Comparison",
       "Pressure Analysis", "Match Explorer", "Methodology & Data Quality", "Final Submission", "RR Auction Targets"]

st.set_page_config(page_title="SupeRR Selector | Cricket Talent Intelligence", page_icon="\U0001F3CF", layout="wide")
apply_theme()


@st.cache_data(show_spinner="Loading verified cricket data")
def csv(path: str, **kwargs) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False, **kwargs)


def available(path: Path) -> bool:
    return path.is_file()


def artifact(name: str, package: bool = False, **kwargs) -> pd.DataFrame:
    path = (SUBMISSION if package else REPORTS) / name
    if not path.is_file():
        return pd.DataFrame()
    try:
        return csv(str(path), **kwargs)
    except Exception as exc:
        st.error(f"Could not read {name}: {exc}")
        return pd.DataFrame()


def markdown(name: str, package: bool = False) -> None:
    read_markdown((SUBMISSION if package else REPORTS) / name)


def source_data() -> dict[str, pd.DataFrame]:
    @st.cache_data(show_spinner="Loading local source tables")
    def _load(root: str):
        base = Path(root) / "data" / "raw"
        result = {}
        for filename in ["matches.csv", "competitions.csv", "ball_by_ball.csv", "playing_eleven.csv", "competition_team_player_mapping.csv"]:
            path = base / filename
            if path.is_file():
                try:
                    result[path.stem] = pd.read_csv(path, low_memory=False)
                except Exception as exc:
                    st.sidebar.warning(f"{filename} could not be loaded: {exc}")
        return result
    return _load(str(ROOT))


def fmt_num(value) -> str:
    return f"{int(value):,}" if pd.notna(value) else ""


def overview(data: dict[str, pd.DataFrame]) -> None:
    st.markdown('<div class="hero"><div class="eyebrow">Cricket Talent Intelligence Platform</div><h1>SupeRR Selector</h1><p>Evidence-led scouting across IPL and T20I, with transparent coverage and ranking limits.</p></div>', unsafe_allow_html=True)
    coverage = artifact("confirmed_scope_coverage_summary.csv")
    overall = artifact("phase5g_overall_batter_top10.csv", package=True)
    batter = artifact("phase5c_batter_rankings.csv")
    bowler = artifact("phase5c_bowler_rankings.csv")
    matches = sum(pd.to_numeric(coverage.match_count, errors="coerce").fillna(0)) if not coverage.empty else len(data.get("matches", []))
    deliveries = sum(pd.to_numeric(coverage.delivery_count, errors="coerce").fillna(0)) if not coverage.empty else len(data.get("ball_by_ball", []))
    eligible = int(batter.competition_ready.fillna(False).astype(bool).sum()) if "competition_ready" in batter else 0
    ready_bowlers = int(bowler.competition_ready.fillna(False).astype(bool).sum()) if "competition_ready" in bowler else 0
    exploratory_bowlers = int((~bowler.competition_ready.fillna(False).astype(bool)).sum()) if "competition_ready" in bowler else 414
    c = st.columns(5)
    c[0].metric("Matches analysed", fmt_num(matches))
    c[1].metric("Delivery records", fmt_num(deliveries))
    c[2].metric("Eligible batter entries", fmt_num(eligible))
    c[3].metric("Bowling ready", fmt_num(ready_bowlers))
    c[4].metric("Bowling exploratory", fmt_num(exploratory_bowlers))
    if not coverage.empty:
        st.subheader("Competition coverage")
        left, right = st.columns([1.25, 1])
        left.plotly_chart(px.bar(coverage, x="format", y="delivery_count", color="format", text="delivery_count",
                                 template="plotly_dark", title="Analysed delivery records by format",
                                 color_discrete_sequence=["#ff5b8d", "#46b6d8"]), width="stretch")
        left.caption("Confirmed scope: IPL and T20I, 2022 onward. Competition counts and coverage come from the project scope audit.")
        right.markdown("#### Evidence status")
        right.info(f"**IPL:** {int(coverage.loc[coverage.format.eq('IPL'),'match_count'].sum()):,} matches  {int(coverage.loc[coverage.format.eq('IPL'),'delivery_count'].sum()):,} deliveries\n\n**T20I:** {int(coverage.loc[coverage.format.eq('T20I'),'match_count'].sum()):,} matches  {int(coverage.loc[coverage.format.eq('T20I'),'delivery_count'].sum()):,} deliveries")
        right.warning("Bowling metrics are constrained by incomplete run attribution and legal-ball semantics. No competition-ready bowler is supported.")
    if not overall.empty:
        st.subheader("Overall Batter Top 10")
        view = overall[[c for c in ["rank", "player_name", "player_id", "mean_within_format_percentile", "formats", "mean_pressure_matches", "mean_consistency_factor"] if c in overall.columns]].copy()
        st.dataframe(view, hide_index=True, width="stretch", height=390)
        st.caption("Authoritative Phase 5G order, independently validated in Phase 5H. Percentile aggregation does not pool raw IPL and T20I scores.")
    with st.expander("Data quality and methodology signals"):
        summary_path = REPORTS / "phase5d_audit_summary.json"
        if summary_path.is_file():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            st.write(f"Phase 5D validated batter candidates: **{summary.get('validated_batter_candidates', 'Unavailable')}**. Bowling candidates validated: **{summary.get('bowler_candidates_validated', 0)}**.")
        st.write("Source data remain local and unchanged. Metrics are shown only where their definitions and denominators are supported.")


def rankings() -> None:
    page_header("Batter Rankings", "Authoritative overall list from the validated Phase 5G and Phase 5H package.")
    df = artifact("phase5g_overall_batter_top10.csv", package=True)
    if df.empty:
        st.info("The validated overall Batter Top 10 artifact is unavailable.")
        return
    st.caption("Ranking order is preserved exactly as submitted. Overall scores are mean within-format percentiles of Phase 5C scores; format scores are not pooled.")
    rows = []
    for _, row in df.iterrows():
        evidence = json.loads(row.format_evidence_json) if pd.notna(row.get("format_evidence_json")) else []
        fmt_parts = []
        stability_parts = []
        for item in evidence:
            fmt_parts.append(f"{item.get('format')}: score {item.get('phase5c_score', float('nan')):.3f}, {item.get('pressure_matches', 0)} pressure matches / {item.get('baseline_matches', 0)} baseline matches")
            stability_parts.append(f"{item.get('format')}: {item.get('stability_flag', 'not reported')}; leave-one-match {item.get('leave_one_match_top10_rate', float('nan')):.0%}; leave-one-season {item.get('leave_one_season_top10_rate', float('nan')):.0%}")
        rows.append({"Rank": row.get("rank"), "Player": row.get("player_name"), "Player ID": row.get("player_id"),
                     "Overall percentile": row.get("mean_within_format_percentile"), "Formats": row.get("formats"),
                     "Pressure matches (mean)": row.get("mean_pressure_matches"), "Baseline matches (mean)": row.get("mean_baseline_matches"),
                     "Consistency factor": row.get("mean_consistency_factor"), "Exposure shrinkage": row.get("mean_exposure_shrinkage"),
                     "Stability": "See Phase 5D/5G audit", "Format evidence": "  ".join(fmt_parts)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    stability = artifact("phase5g_cross_format_stability.csv", package=True)
    if not stability.empty:
        st.subheader("Ranking stability")
        st.dataframe(stability, hide_index=True, width="stretch")
    with st.expander("Ranking methodology and independent validation"):
        markdown("phase5h_methodology_report.md", package=True)
    with st.expander("Phase 5C format rankings and validation"):
        fmt = st.radio("Format evidence", ["IPL", "T20I"], horizontal=True, key="rank_fmt")
        ranked = artifact("phase5c_batter_rankings.csv")
        if not ranked.empty:
            st.dataframe(ranked.loc[ranked.format.eq(fmt) & ranked.competition_ready.fillna(False)].sort_values("rank"), hide_index=True, width="stretch")
        markdown("phase5c_ranking_validation.md")
    with st.expander("Phase 5D independent validation and stability"):
        markdown("phase5d_independent_validation.md")
        stability5d = artifact("phase5d_batter_top10_stability.csv")
        if not stability5d.empty: st.dataframe(stability5d, hide_index=True, width="stretch")
    with st.expander("Phase 5H readiness and limitations"):
        markdown("phase5h_submission_readiness.md", package=True)


def bowling() -> None:
    page_header("Bowling Analysis", "Transparent bowling evidence, metric coverage and current readiness decision.")
    c = st.columns(3)
    c[0].metric("Competition-ready candidates", "0")
    c[1].metric("Exploratory profiles", "414")
    c[2].metric("Verified-chase eligible", "0")
    st.warning("No Bowler Top 10 is supported. Exploratory profiles are not recommendations.")
    st.markdown("#### Reliably observable\n- Recognized bowler-credit wicket events under the documented dismissal rule.\n- Dot and boundary outcomes on ordinary-delivery subsets.\n- Limited event counts and exposure summaries.")
    st.markdown("#### Blocked by source semantics\n- Bowler-conceded runs: total runs and complete typed extras attribution are absent.\n- Complete legal-ball and overs denominators: delivery legality is incomplete and partly inferred.\n- Conventional economy and bowling strike rate: required numerator/denominator are unavailable.")
    st.markdown("Verified chase-state evidence covers only 31 IPL rows (0.074%) and 261 T20I rows (0.524%) in the audit scope; no player meets both inherited pressure and baseline exposure floors.")
    audit = artifact("phase5h_bowling_metric_audit.csv", package=True)
    if not audit.empty:
        st.subheader("Metric evidence audit")
        fmt = st.selectbox("Format", ["All", "IPL", "T20I"], key="bowl_fmt")
        view = audit if fmt == "All" else audit.loc[audit.format.eq(fmt)]
        st.dataframe(view, hide_index=True, width="stretch")
    with st.expander("Phase 5E model and sensitivity evidence"):
        markdown("phase5e_bowling_model.md")
        markdown("phase5e_batter_sensitivity_review.md")
        markdown("phase5e_submission_strategy.md")
    with st.expander("Full bowling audit"):
        markdown("phase5h_bowling_final_audit.md", package=True)


def discovery(data: dict[str, pd.DataFrame]) -> None:
    page_header("Player Discovery", "Search confirmed competition player records and explore supported descriptive profiles.")
    exposure = artifact("player_exposure_summary.csv")
    bat = artifact("batter_performance_profile.csv")
    bowl = artifact("bowler_performance_profile.csv")
    if exposure.empty:
        st.info("Player exposure artifact is unavailable. No profile statistics are inferred from partial source tables.")
        return
    q = st.text_input("Search player name or ID")
    formats = sorted(exposure.format.dropna().unique().tolist())
    f = st.multiselect("Format", formats, default=formats)
    view = exposure.loc[exposure.format.isin(f)].copy()
    if "role" in view:
        roles = sorted(view.role.dropna().astype(str).unique().tolist())
        selected_roles = st.multiselect("Role", roles, default=roles)
        view = view.loc[view.role.astype(str).isin(selected_roles)]
    if q:
        view = view.loc[view.player_name.astype(str).str.contains(q, case=False, na=False) | view.player_id.astype(str).str.contains(q, case=False, na=False)]
    st.caption(f"{len(view):,} player-format records")
    st.dataframe(view[[c for c in ["player_id", "player_name", "role", "format", "matches", "observed_deliveries", "descriptive_profile_usable", "sufficient_evidence_for_future_pressure_comparison"] if c in view]], hide_index=True, width="stretch", height=420)
    if len(view):
        ids = view.player_id.astype(str).unique().tolist()
        selected = st.selectbox("Open player profile", ids, format_func=lambda pid: str(view.loc[view.player_id.astype(str).eq(pid), "player_name"].iloc[0]) + f"  {pid}")
        profile = pd.concat([bat, bowl], ignore_index=True) if not bat.empty and not bowl.empty else (bat if not bat.empty else bowl)
        if not profile.empty and "player_id" in profile:
            p = profile.loc[profile.player_id.astype(str).eq(selected)]
            if not p.empty:
                st.subheader("Descriptive profile")
                st.dataframe(p, hide_index=True, width="stretch")
    with st.expander("Profile definitions and limits"):
        markdown("player_analytics_limitations.md")


def comparison() -> None:
    page_header("Player Comparison", "Compare available descriptive profiles within a format and role.")
    bat = artifact("batter_performance_profile.csv")
    bowl = artifact("bowler_performance_profile.csv")
    exposure = artifact("player_exposure_summary.csv")
    if bat.empty and bowl.empty:
        st.info("Validated player profile artifacts are unavailable.")
        return
    fmt = st.radio("Format", ["IPL", "T20I"], horizontal=True)
    role = st.radio("Role", ["Batter", "Bowler"], horizontal=True)
    profile = bat if role == "Batter" else bowl
    choices = profile.loc[profile.format.eq(fmt), ["player_id", "player_name"]].drop_duplicates()
    if choices.empty:
        st.info("No profiles exist for this selection.")
        return
    names = dict(zip(choices.player_id.astype(str), choices.player_name.astype(str)))
    selected = st.multiselect("Select up to four players", choices.player_id.astype(str).tolist(), max_selections=4,
                              format_func=lambda pid: f"{names.get(pid, pid)}  {pid}")
    rows = profile.loc[profile.player_id.astype(str).isin(selected) & profile.format.eq(fmt)].copy()
    if not rows.empty:
        metrics = [c for c in rows.select_dtypes(include="number") if rows[c].notna().any()]
        if metrics:
            metric = st.selectbox("Chart metric", metrics)
            st.plotly_chart(px.bar(rows, x="player_name", y=metric, color="cohort" if "cohort" in rows else None, barmode="group", template="plotly_dark", title=metric.replace("_", " ").title()), width="stretch")
        st.dataframe(rows, hide_index=True, width="stretch")
    if not exposure.empty:
        st.caption("Exposure summaries remain available on Player Discovery. Descriptive cohorts do not establish psychological pressure or player rankings.")


def pressure_analysis() -> None:
    page_header("Pressure Analysis", "Verified scoreboard state and contextual proxies are presented as separate evidence classes.")
    coverage = artifact("pressure_coverage.csv")
    matrix = artifact("metric_feasibility.csv")
    if coverage.empty:
        st.info("Pressure artifacts are unavailable. Run the documented pressure analysis pipeline to generate them.")
        markdown("pressure_feasibility_report.md")
        return
    st.warning("Verified chase pressure means known-state RRR > CRR. Wicket/phase and delivery context are proxies; none prove psychological pressure. Unknown match states are excluded.")
    st.plotly_chart(px.bar(coverage, x="definition", y="delivery_coverage_pct", color="definition", template="plotly_dark", title="Coverage by pressure definition", hover_data=[c for c in ["delivery_rows_covered", "delivery_rows_total", "matches_covered"] if c in coverage]), width="stretch")
    st.dataframe(coverage, hide_index=True, width="stretch")
    if not matrix.empty:
        with st.expander("Metric feasibility"): st.dataframe(matrix, hide_index=True, width="stretch")
    with st.expander("Pressure methodology"): markdown("pressure_scoring_methodology.md")
    with st.expander("Coverage and gaps"): markdown("pressure_evidence_gap_analysis.md")


def match_explorer(data: dict[str, pd.DataFrame]) -> None:
    page_header("Match Explorer", "Inspect match metadata and validated reconstructed states when available.")
    matches = data.get("matches", pd.DataFrame())
    comps = data.get("competitions", pd.DataFrame())
    if not matches.empty:
        view = matches.copy()
        if "comp_id" in view and not comps.empty and "comp_id" in comps:
            view = view.merge(comps[[c for c in ["comp_id", "comp_name", "match_format", "season"] if c in comps]], on="comp_id", how="left")
        search = st.text_input("Find a team, venue or match ID")
        if search:
            mask = view.astype(str).apply(lambda col: col.str.contains(search, case=False, na=False)).any(axis=1)
            view = view.loc[mask]
        st.dataframe(view, hide_index=True, width="stretch", height=360)
    state_path = ROOT / "data" / "processed" / "match_state_deliveries.csv.gz"
    quality_path = REPORTS / "match_state_quality.csv"
    if not state_path.is_file():
        st.info("Reconstructed delivery states are not available. Match metadata above remain searchable.")
        return
    try:
        state = csv(str(state_path))
        ids = sorted(state.match_id.dropna().unique().tolist())
        mid = st.selectbox("Reconstructed match", ids)
        m = state.loc[state.match_id.eq(mid)].copy()
        innings = st.selectbox("Innings", sorted(m.innings.dropna().unique().tolist()))
        m = m.loc[m.innings.eq(innings)].sort_values("sequence")
        score_cov = 100 * m.score_known.fillna(False).mean() if len(m) else 0
        c = st.columns(2); c[0].metric("Known score-state coverage", f"{score_cov:.1f}%")
        final = m.innings_final_score_if_known.dropna(); c[1].metric("Derived innings total", str(int(final.iloc[-1])) if len(final) else "Unresolved")
        st.warning("These are provisional reconstructed states, not official scorecard totals. State becomes unknown after ambiguous extras accounting.")
        if m.score_known.fillna(False).any():
            st.plotly_chart(px.line(m, x="sequence", y="score_before", template="plotly_dark", title="Known pre-delivery score state"), width="stretch")
        if quality_path.is_file():
            quality = csv(str(quality_path)); row = quality.loc[quality.match_id.eq(mid)]
            if not row.empty: st.dataframe(row, hide_index=True, width="stretch")
    except Exception as exc:
        st.error(f"Match state data could not be loaded: {exc}")


def methodology() -> None:
    page_header("Methodology & Data Quality", "Review source coverage, field quality, eligibility rules and analytical limitations.")
    coverage = artifact("confirmed_scope_coverage_summary.csv")
    inventory = artifact("dataset_inventory.csv")
    quality = artifact("data_quality_report.csv")
    if not coverage.empty:
        st.subheader("Confirmed analysis scope"); st.dataframe(coverage, hide_index=True, width="stretch")
    if not inventory.empty:
        st.subheader("Dataset inventory"); st.dataframe(inventory, hide_index=True, width="stretch")
    if not quality.empty:
        st.subheader("Data quality checks"); st.dataframe(quality, hide_index=True, width="stretch")
    tabs = st.tabs(["Ranking method", "Bowling limits", "Source and scope", "Earlier analysis", "Match and eligibility audits"])
    with tabs[0]: markdown("phase5h_methodology_report.md", package=True)
    with tabs[1]: markdown("phase5h_bowling_final_audit.md", package=True)
    with tabs[2]:
        markdown("accepted_data_dictionary.md")
        markdown("confirmed_scope_coverage.md")
    with tabs[3]:
        markdown("phase5a_available_data_analysis.md")
        markdown("phase5a_ranking_sensitivity.md")
        markdown("phase5e_batter_sensitivity_review.md")
    with tabs[4]:
        markdown("match_acceptance_report.md")
        markdown("player_eligibility_report.md")
        markdown("match_state_validation.md")


def final_submission() -> None:
    page_header("Final Submission", "Validated submission package, readiness status and supporting evidence.")
    readme = SUBMISSION / "README.md"
    if readme.is_file(): st.markdown(readme.read_text(encoding="utf-8"))
    overall = artifact("phase5g_overall_batter_top10.csv", package=True)
    if not overall.empty:
        st.subheader("Official overall Batter Top 10")
        st.dataframe(overall.drop(columns=["format_evidence_json", "limitations"], errors="ignore"), hide_index=True, width="stretch")
    st.subheader("Bowling disposition")
    st.warning("Required Bowler Top 10 unresolved: 0 competition-ready candidates, 414 exploratory profiles. No list is fabricated or promoted.")
    with st.expander("Readiness and methodology"): markdown("phase5h_submission_readiness.md", package=True)
    with st.expander("Submission checklist"): markdown("phase5g_final_action_checklist.md", package=True)


data = source_data()
st.sidebar.markdown("## SupeRR Selector")
st.sidebar.caption("Cricket Talent Intelligence Platform")
page = st.sidebar.radio("Workspace", NAV, label_visibility="collapsed")
st.sidebar.divider()
st.sidebar.caption("IPL + T20I  2022 onward\nEvidence-led scouting")

if page == "Overview": overview(data)
elif page == "Player Discovery": discovery(data)
elif page == "Batter Rankings": rankings()
elif page == "Bowling Analysis": bowling()
elif page == "Player Comparison": comparison()
elif page == "Pressure Analysis": pressure_analysis()
elif page == "Match Explorer": match_explorer(data)
elif page == "Methodology & Data Quality": methodology()
elif page == "Final Submission": final_submission()
elif page == "RR Auction Targets": render_auction_targets(ROOT, artifact, markdown)








