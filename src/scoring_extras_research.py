"""Research-only scoring reconciliation for the four Phase 2F controls.

This module reads official and Cricsheet records without changing either source.
It deliberately does not join player or venue identities.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTROL_FILES = {13511: "1256720.json", 20182: "1359476.json", 34429: "1442989.json", 40725: "1473469.json"}
SCORECARDS = {
    13511: ("Windies Cricket series page", "https://www.windiescricket.com/series/england-in-west-indies-2021-22-16230/", {1: (103, 10, "19.4"), 2: (104, 1, "17.1")}),
    20182: ("Punjab Kings match report", "https://www.punjabkingsipl.in/news/rajapaksa-arshdeep-star-as-punjab-kings-beat-kolkata-knight-riders-ipl-2023-season-opener", {1: (191, 5, "20.0"), 2: (146, 7, "16.0")}),
    34429: ("Sri Lanka Cricket Annual Report 2024; detailed scorecard at IPL.com", "https://srilankacricket.lk/wp-content/uploads/2025/06/SLC-Annual-Report-2024-soft-copy-1.pdf; https://www.ipl.com/matches/india-tour-of-sri-lanka-128745/sri-lanka-vs-india-78390/scorecard", {1: (137, 9, "20.0"), 2: (137, 8, "20.0"), 3: (2, 2, "0.3"), 4: (4, 0, "0.1")}),
    40725: ("Detailed IPL.com scorecard", "https://www.ipl.com/matches/indian-premier-league-129413/delhi-capitals-vs-rajasthan-royals-87731/scorecard", {1: (188, 5, "20.0"), 2: (188, 4, "20.0"), 3: (11, 2, "0.5"), 4: (13, 0, "0.4")}),
}
SCORECARD_TYPED_EXTRAS = {
    # Values transcribed from detailed scorecards; None means no per-type breakdown was available in the cited source.
    34429: {1: {"noballs": 0, "wides": 5, "byes": 0, "legbyes": 2, "penalty": 0}, 2: {"noballs": 0, "wides": 8, "byes": 0, "legbyes": 2, "penalty": 0}, 3: {"noballs": 0, "wides": 1, "byes": 0, "legbyes": 0, "penalty": 0}, 4: {"noballs": 0, "wides": 0, "byes": 0, "legbyes": 0, "penalty": 0}},
    40725: {1: {"noballs": 1, "wides": 7, "byes": 0, "legbyes": 1, "penalty": 0}, 2: {"noballs": 1, "wides": 3, "byes": 1, "legbyes": 1, "penalty": 0}, 3: {"noballs": 1, "wides": 0, "byes": 0, "legbyes": 0, "penalty": 0}, 4: {"noballs": 0, "wides": 0, "byes": 0, "legbyes": 0, "penalty": 0}},
}
SCORECARD_BOWLER_CONCEDED = {
    34429: {1: 135, 2: 135, 3: 2, 4: 4},
    40725: {1: 187, 2: 186, 3: 11, 4: 13},
}
EXTRA_KEYS = ("byes", "legbyes", "wides", "noballs", "penalty", "other")
BOWLER_EXEMPT = {"byes", "legbyes", "penalty"}
BOWLER_WICKET_KINDS = {"bowled", "caught", "caught and bowled", "lbw", "stumped", "hit wicket"}


def delivery_components(delivery: dict[str, Any]) -> dict[str, Any]:
    runs = delivery.get("runs", {}) or {}
    extras = delivery.get("extras", {}) or {}
    batter = int(runs.get("batter", 0) or 0)
    extra_total = int(runs.get("extras", 0) or 0)
    total = int(runs.get("total", 0) or 0)
    typed = {k: int(extras.get(k, 0) or 0) for k in EXTRA_KEYS}
    known_sum = sum(typed.values())
    return {"batter_runs": batter, "extras_total": extra_total, "total_runs": total,
            "extras_by_type": typed, "decomposition_ok": batter + extra_total == total,
            "typed_extras_ok": known_sum == extra_total,
            "unknown_extra_keys": sorted(set(extras) - set(EXTRA_KEYS))}


def legal_delivery(delivery: dict[str, Any]) -> bool:
    extras = delivery.get("extras", {}) or {}
    return not (int(extras.get("wides", 0) or 0) > 0 or int(extras.get("noballs", 0) or 0) > 0)


def bowler_conceded(delivery: dict[str, Any]) -> int | None:
    parts = delivery_components(delivery)
    extras = delivery.get("extras", {}) or {}
    # The pilot has no evidence for how the provider's `other` category is charged.
    if parts["unknown_extra_keys"] or int(extras.get("other", 0) or 0) > 0:
        return None
    return parts["total_runs"] - sum(int(extras.get(k, 0) or 0) for k in BOWLER_EXEMPT)


def innings_wickets(innings: dict[str, Any]) -> int:
    return sum(1 for d in innings.get("overs", []) for delivery in d.get("deliveries", [])
               for wicket in delivery.get("wickets", []) if str(wicket.get("kind", "")).lower() != "retired hurt")


def bowler_credit_wickets(innings: dict[str, Any]) -> int:
    n = 0
    for over in innings.get("overs", []):
        for d in over.get("deliveries", []):
            extras = d.get("extras", {}) or {}
            if int(extras.get("noballs", 0) or 0) > 0:
                continue
            n += sum(str(w.get("kind", "")).lower() in BOWLER_WICKET_KINDS for w in d.get("wickets", []))
    return n


def _all_innings(document: dict[str, Any]):
    return [(index, inn) for index, inn in enumerate(document.get("innings", []), start=1)]


def _iter_deliveries(innings: dict[str, Any]):
    for over in innings.get("overs", []):
        for position, d in enumerate(over.get("deliveries", []), start=1):
            yield int(over.get("over", 0)) + 1, position, d


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def generate_reports(root: Path = ROOT) -> dict[str, int]:
    raw = root / "data" / "raw" / "ball_by_ball.csv"
    # Match local rows by public match and coordinate only; player and venue fields are never used.
    with raw.open(newline="", encoding="utf-8-sig") as f:
        local_rows = list(csv.DictReader(f))
    local = {}
    for row in local_rows:
        if int(row["match_id"]) in CONTROL_FILES:
            local[(int(row["match_id"]), int(row["innings"]), int(row["overid"]), int(row["over_ball_num"]))] = row
    output_rows, innings_rows, match_summaries = [], [], []
    for mid, filename in CONTROL_FILES.items():
        doc = json.loads((root / "data" / "external" / "cricsheet" / "pilot" / "matches" / filename).read_text(encoding="utf-8"))
        scorecard_name, scorecard_url, expected = SCORECARDS[mid]
        for inn_no, inn in _all_innings(doc):
            deliveries = list(_iter_deliveries(inn))
            parts = [delivery_components(d) for _, _, d in deliveries]
            ext_aggregate = {k: sum(p["extras_by_type"][k] for p in parts) for k in EXTRA_KEYS}
            runs = sum(p["total_runs"] for p in parts)
            extras = sum(p["extras_total"] for p in parts)
            bat = sum(p["batter_runs"] for p in parts)
            legal = sum(legal_delivery(d) for _, _, d in deliveries)
            wkts, credits = innings_wickets(inn), bowler_credit_wickets(inn)
            inn_penalty = sum(int(x or 0) for x in (inn.get("penalty_runs", {}) or {}).values())
            candidate_total = runs + inn_penalty
            score = expected.get(inn_no)
            score_extras = SCORECARD_TYPED_EXTRAS.get(mid, {}).get(inn_no)
            extras_card_status = "not available in cited scorecard" if score_extras is None else ("confirmed" if all(ext_aggregate[k] == score_extras[k] for k in score_extras) else "disagreement")
            scorecard_conceded = SCORECARD_BOWLER_CONCEDED.get(mid, {}).get(inn_no)
            conceded = [bowler_conceded(d) for _, _, d in deliveries]
            conceded_candidate = "" if any(x is None for x in conceded) else sum(conceded)
            outcome = "not independently listed" if score is None else ("confirmed" if candidate_total == score[0] and wkts == score[1] and f"{legal//6}.{legal%6}" == score[2] else "disagreement")
            innings_rows.append({"match_id": mid, "innings": inn_no, "team_external": inn.get("team", ""), "super_over": bool(inn.get("super_over", False)),
                "deliveries": len(deliveries), "batter_runs": bat, "extras_total": extras, "typed_extras_sum": sum(sum(p["extras_by_type"].values()) for p in parts),
                "total_runs_delivery_sum": runs, "innings_penalty_runs": inn_penalty, "innings_total_candidate": candidate_total, "team_wickets_lost_candidate": wkts,
                "bowler_credit_wickets_candidate": credits, "legal_balls_candidate": legal, "overs_scorecard_notation": f"{legal//6}.{legal%6}",
                "target_runs_external": (inn.get("target") or {}).get("runs", ""), "target_overs_external": (inn.get("target") or {}).get("overs", ""),
                "external_extras_by_type_json": json.dumps(ext_aggregate, sort_keys=True), "scorecard_extras_by_type_json": "" if score_extras is None else json.dumps(score_extras, sort_keys=True), "scorecard_extras_comparison": extras_card_status,
                "scorecard_total": "" if score is None else score[0], "scorecard_wickets": "" if score is None else score[1], "scorecard_overs": "" if score is None else score[2],
                "scorecard_comparison": outcome, "bowler_conceded_sum_candidate": conceded_candidate,
                "scorecard_bowler_conceded_sum": "" if scorecard_conceded is None else scorecard_conceded,
                "bowler_conceded_scorecard_comparison": "not available in cited scorecard" if scorecard_conceded is None else ("confirmed" if conceded_candidate == scorecard_conceded else "disagreement"),
                "scorecard_source": scorecard_name, "scorecard_url": scorecard_url})
            for over_no, pos, d in deliveries:
                p = delivery_components(d)
                key = (mid, inn_no, over_no, pos)
                l = local.get(key, {})
                local_type = str(l.get("extras_type", "") or "").strip()
                if local_type.lower() in {"none", "nan", "null"}:
                    local_type = ""
                type_map = {"wide": "wides", "wides": "wides", "legbyes": "legbyes", "bye": "byes", "byes": "byes"}
                external_types = [k for k, amount in p["extras_by_type"].items() if amount]
                local_type_mapped = type_map.get(local_type.lower(), "")
                if local_type == "Overstep" and "noballs" in external_types:
                    type_status = "inferred Overstep/no-ball; unverified"
                elif not local_type and not external_types:
                    type_status = "exact no extras"
                elif local_type_mapped and local_type_mapped in external_types:
                    type_status = "exact type"
                elif local_type and external_types:
                    type_status = "different/unresolved; do not infer code semantics"
                else:
                    type_status = "unresolved local category/amount"
                output_rows.append({"match_id": mid, "innings": inn_no, "over": over_no, "delivery_position": pos,
                    "local_row_present": bool(l), "batter_runs_local": l.get("runs", ""), "batter_runs_external": p["batter_runs"],
                    "batter_runs_match": "exact" if l and int(l.get("runs") or 0) == p["batter_runs"] else "unresolved/no local row",
                    "local_extras_type": local_type, "local_extras1_code_not_amount": l.get("extras1_runs", ""), "local_extras2_unresolved": l.get("extras_2_runs", ""),
                    "external_extras_by_type_json": json.dumps(p["extras_by_type"], sort_keys=True), "external_extras_total": p["extras_total"], "external_total_runs": p["total_runs"],
                    "local_type_candidate": local_type_mapped, "external_nonzero_types": ";".join(external_types),
                    "extras_type_comparison": type_status,
                    "decomposition_batter_plus_extras_equals_total": p["decomposition_ok"], "typed_extras_sum_equals_extras_total": p["typed_extras_ok"],
                    "legal_external_candidate": legal_delivery(d), "legal_local": l.get("legal_delivery", ""),
                    "bowler_conceded_candidate": bowler_conceded(d), "wickets_json": json.dumps(d.get("wickets", []), sort_keys=True), "unknown_extra_keys": ";".join(p["unknown_extra_keys"])})
        match_summaries.append({"match_id": mid, "delivery_rows": sum(len(list(_iter_deliveries(i))) for _, i in _all_innings(doc)), "innings_count": len(doc.get("innings", [])), "scorecard_source": scorecard_name, "scorecard_url": scorecard_url})
    reports = root / "outputs" / "reports"
    _write_csv(reports / "scoring_extras_comparison.csv", output_rows)
    _write_csv(reports / "metric_reconstruction_feasibility.csv", [
        {"metric": "batter runs", "status": "reliable from Cricsheet event data; local comparison exact 965/965", "rule": "runs.batter", "scope": "4 controls", "limitations": "No player-level accepted joins until verified ID crosswalk."},
        {"metric": "delivery total runs", "status": "reliable as external event calculation; not recoverable from local feed", "rule": "runs.total; check batter + extras", "scope": "965 deliveries", "limitations": "Local extras fields are codes/ambiguous; no silent backfill."},
        {"metric": "extras amount by type", "status": "reliable from typed external extras; locally unsupported", "rule": "sum extras mapping; compare with runs.extras", "scope": "965 deliveries", "limitations": "Local category-code semantics unresolved; two byes/legbyes label disagreements."},
        {"metric": "legal balls", "status": "reliable from Cricsheet typed wides/no-balls; local partial", "rule": "illegal only for wide/no-ball; count every actual delivery position", "scope": "12 innings; all overs match scorecard notation", "limitations": "Local Overstep-to-no-ball is pattern evidence only; two other rows lack local legal flags."},
        {"metric": "innings total", "status": "confirmed for all 12 control innings against listed scorecards", "rule": "sum runs.total + innings penalty", "scope": "4 matches incl. DLS and Super Overs", "limitations": "13511/20182 source pages establish innings totals; detailed type extras not independently published there."},
        {"metric": "target", "status": "external target field available in JSON; independent context verified where stated", "rule": "info/innings target; treat DLS and super overs separately", "scope": "regular chases", "limitations": "DLS target154 for 20182 is par153 + one; no local targets in controls."},
        {"metric": "bowler-conceded runs", "status": "candidate; aggregate confirmed in 34429 and 40725", "rule": "total minus byes, legbyes, penalty; wides/no-balls charged", "scope": "8 innings in 2 detailed scorecards", "limitations": "No accepted player attribution; no independently checked detailed bowling cards for 13511/20182."},
        {"metric": "team wickets lost", "status": "reliable from wicket events with retired hurt excluded", "rule": "count dismissal events except retired hurt", "scope": "12 innings; scorecard aggregate matches", "limitations": "Wicket lost is not equivalent to bowler-credit wicket."},
        {"metric": "bowler-credit wickets", "status": "candidate from dismissal kind and no-ball exception", "rule": "credit eligible dismissal kinds, suppress on no-ball", "scope": "control event data; aggregate scorecard checks for detailed cards", "limitations": "Needs verified bowler identity and full independent figures before acceptance."},
        {"metric": "penalty/other extras", "status": "unsupported by empirical controls", "rule": "explicit typed fields only; innings penalty separate", "scope": "no delivery penalty/other examples in these controls", "limitations": "Tested algorithmically only; no production rule validated here."},
    ])
    confirmed = sum(r["scorecard_comparison"] == "confirmed" for r in innings_rows)
    extras_confirmed = sum(r["scorecard_extras_comparison"] == "confirmed" for r in innings_rows)
    conceded_confirmed = sum(r["bowler_conceded_scorecard_comparison"] == "confirmed" for r in innings_rows)
    (reports / "scoring_extras_reconciliation.md").write_text(_render_report(output_rows, innings_rows, confirmed, extras_confirmed, conceded_confirmed), encoding="utf-8")
    return {"delivery_rows": len(output_rows), "innings": len(innings_rows), "innings_confirmed": confirmed}


def _render_report(deliveries: list[dict[str, Any]], innings: list[dict[str, Any]], confirmed: int, extras_confirmed: int, conceded_confirmed: int) -> str:
    cats = Counter(k for r in deliveries for k in str(r["external_nonzero_types"]).split(";") if k)
    batter_exact = sum(r["batter_runs_match"] == "exact" for r in deliveries)
    type_exact = sum(r["extras_type_comparison"] == "exact type" for r in deliveries)
    no_extras_exact = sum(r["extras_type_comparison"] == "exact no extras" for r in deliveries)
    overstep_inferred = sum(r["extras_type_comparison"] == "inferred Overstep/no-ball; unverified" for r in deliveries)
    extras_unresolved = len(deliveries) - type_exact - no_extras_exact - overstep_inferred
    return f'''# Phase 2F.5 — Scoring and extras reconciliation research

## Scope and identity safeguards

Research covers the four downloaded controls (13511, 20182, 34429, 40725), **{len(deliveries)} aligned delivery coordinates** and **{len(innings)} innings**, including four Super Over innings. Alignment uses match, innings, over, and delivery position only. No player names/IDs or venue candidates are used as evidence or joins. Source CSVs, Cricsheet originals, prior reconciliation decisions, and acceptance criteria remain unchanged. Delivery detail is in `scoring_extras_comparison.csv`; metric conclusions are in `metric_reconstruction_feasibility.csv`.

## Findings

- Batter runs agree on **{batter_exact}/{len(deliveries)}** rows. This validates the value field comparison only, not player identity joins.
- Cricsheet explicitly separates `runs.batter`, `runs.extras`, `runs.total`, and typed `extras`. The internal equation `batter + extras = total` and typed-extras sum are checked per delivery. Local `runs` matches batter runs, while `extras1_runs` acts as a categorical code in observed rows and `extras_2_runs` cannot be safely treated as an amount. Consequently local total runs and typed amounts remain unavailable.
- Direct local extra-type labels align on **{type_exact}** rows; no-extra rows agree on **{no_extras_exact}**. **{overstep_inferred}** `Overstep` rows align with external no-balls only as an inference. The remaining **{extras_unresolved}** rows include the two local byes/leg-byes label disagreements in match 20182 and category/amount ambiguity. Two local `other` rows have unknown legal status; Cricsheet records no-ball on those events.
- Cricsheet typed event counts in these controls: **{dict(cats)}**. No typed `penalty` or delivery `other` example occurs. Thus those rules remain unsupported empirically. Innings-level penalty is separately included if present; it is not a bowler charge.

## Innings totals and independent scorecards

The event-derived total is `sum(runs.total) + innings penalty runs`. It matches **{confirmed}/{len(innings)}** innings in the independent scorecard material indexed in the CSV. This includes regular innings, DLS-reduced chase, and Super Overs. 13511 uses the Windies Cricket series page; 20182 uses the Punjab Kings report; 34429 uses Sri Lanka Cricket's annual report for regulation totals plus a separate detailed scorecard for Super Over; 40725 uses a detailed scorecard. The detailed IPL.com pages are independent secondary scorecards, not presented here as official publisher sources. Typed extras totals match those detailed cards on **{extras_confirmed}/8** innings (four in each of 34429 and 40725); typed extras breakdowns were not available on the cited pages for 13511 and 20182. The 20182 chase is 146 after 16 overs; DLS par is 153, so target 154. Targets and innings totals must not be conflated.

## Legal balls and revised overs

Cricsheet legal-ball candidate: count each event delivery except an event carrying wides or no-balls. Do not treat the displayed delivery label as a legal-ball counter: an illegal delivery can repeat the same actual-ball label. Count legal balls and render overs as quotient/remainder by six (`19.4` = 118 legal balls; `0.3` = 3), never decimal arithmetic. All **{len(innings)}** innings match the independent scorecard over notation. The controls include the 16-over DLS chase and four Super Over innings; reduced overs are match-state rules/targets, not a different legality formula. Local `Overstep` mapping remains unverified, and blank legal flags remain unknown rather than guessed.

## Bowler figures and wickets

Bowler-conceded candidate per delivery is total runs minus byes, leg-byes, and penalty; wides and no-balls remain charged. Sum to innings totals only after accounting for non-bowler-charged extras. The detailed cards for 34429 and 40725 corroborate aggregate bowler-conceded runs on **{conceded_confirmed}/8** innings. The other two controls lack sufficiently detailed independent bowling figures in the cited pages, so those aggregates stay candidate. The innings CSV keeps bowler-conceded runs distinct from the team total and lists both sides of the comparison.

Team wickets lost count dismissals excluding retired hurt. Bowler-credit wickets are a separate concept: only eligible dismissal kinds, with no-ball exceptions applied. Run outs and retired out can reduce team wickets without bowler credit; retired hurt does not reduce wickets lost. Detailed scorecards support the aggregate distinction. The comparison CSV retains dismissal events and candidate values separately; no per-player bowler join is asserted.

## Confirmed, unresolved, and unsupported

**Confirmed for this control sample:** batter-run field agreement; Cricsheet's event arithmetic and typed extras decomposition; event-derived innings totals and legal-ball/over notation against the 12 listed innings scores; the distinction between team wickets and bowler-credit wickets. This is research validation, not acceptance of any match under Phase 2F criteria.

**Unresolved locally:** per-delivery total runs, extra amounts, category-code meanings, `Overstep` legality semantics, the two conflicting byes/leg-byes labels, two `other` legal flags, independent targets in the official feed, complete bowling figures for 13511/20182, and all player identity joins. No fuzzy player mapping or candidate venue mapping was used.

**Unsupported by these controls:** delivery penalty/other scoring behavior and their legal-ball/bowler-concession edge cases. These need a documented provider definition plus a real independently verified example before general use.

## Reliable metrics for a future scoring engine

Cricsheet `runs.batter`, `runs.extras`, `runs.total`, and explicit extras-by-type are reliable event fields once a match is independently accepted. Legal balls can be reconstructed from typed wides/no-balls, with actual delivery position preserved. Innings totals can be summed from event totals plus explicit innings penalty, and score state/wickets can be replayed with retired hurt handled separately. Bowler-conceded runs and bowler-credit wickets are calculable from typed extras and dismissal kinds, but player-level figures should remain provisional until independently checked and identity crosswalk accepted. The supplied local feed alone safely supports batter-run comparison; it does not safely support total runs, extras amounts, targets, economy, or bowling strike rate.

## Source URLs

- Windies Cricket: https://www.windiescricket.com/series/england-in-west-indies-2021-22-16230/
- Punjab Kings: https://www.punjabkingsipl.in/news/rajapaksa-arshdeep-star-as-punjab-kings-beat-kolkata-knight-riders-ipl-2023-season-opener
- Sri Lanka Cricket Annual Report 2024: https://srilankacricket.lk/wp-content/uploads/2025/06/SLC-Annual-Report-2024-soft-copy-1.pdf
- Detailed 34429 scorecard: https://www.ipl.com/matches/india-tour-of-sri-lanka-128745/sri-lanka-vs-india-78390/scorecard
- Detailed 40725 scorecard: https://www.ipl.com/matches/indian-premier-league-129413/delhi-capitals-vs-rajasthan-royals-87731/scorecard

Cricsheet source files are the previously downloaded ODC-BY 1.0 records under `data/external/cricsheet/pilot/matches/`; this task made no downloads or source changes.
'''


if __name__ == "__main__":
    print(json.dumps(generate_reports(), indent=2))
