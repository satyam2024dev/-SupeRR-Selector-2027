"""Phase 2F.6 match-level acceptance gate and isolated export.

This applies the existing Phase 2E zero-unexplained-difference gate. It does not
modify official source files or reuse candidate identity links as verified IDs.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.scoring_extras_research import (
    SCORECARDS, SCORECARD_TYPED_EXTRAS, _all_innings, _iter_deliveries, delivery_components,
    innings_wickets, legal_delivery,
)

ROOT = Path(__file__).resolve().parents[1]
MANDATORY_GATES = (
    "match_identity", "venue_identity", "player_identity", "delivery_alignment",
    "batter_runs", "typed_extras", "delivery_totals", "legal_balls", "wickets",
    "innings_totals", "targets", "match_result", "bowling_figures",
)
ACCEPTED_COLUMNS = [
    "official_match_id", "external_match_id", "innings", "over", "delivery_position",
    "batter_runs_external", "extras_by_type_json", "extras_total_external", "total_runs_external",
    "legal_delivery_external", "wickets_json", "source_provider", "source_url", "source_filename",
    "source_sha256", "license_attribution", "acceptance_status", "acceptance_reason",
]


def decide_match(gates: dict[str, str]) -> tuple[str, str]:
    """Return accepted/rejected/unresolved; only explicit pass clears a gate."""
    failed = [g for g in MANDATORY_GATES if gates.get(g) == "fail"]
    unresolved = [g for g in MANDATORY_GATES if gates.get(g) != "pass" and g not in failed]
    if failed:
        return "rejected", "confirmed failed mandatory checks: " + "; ".join(failed)
    if unresolved:
        return "unresolved", "mandatory checks lack verified evidence: " + "; ".join(unresolved)
    return "accepted", "all mandatory Phase 2E checks passed with zero unexplained differences"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _int(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_true(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _pass_or_unresolved(ok: bool, supported: bool) -> str:
    return "pass" if ok and supported else "unresolved"


def _scorecard_check(match_id: int, external_path: Path | None) -> tuple[str, int, int]:
    """Check event-derived score, wickets and overs against the Phase 2F.5 scorecard facts."""
    expected = SCORECARDS.get(match_id)
    if not expected or not external_path or not external_path.is_file():
        return "unresolved", 0, 0
    try:
        doc = json.loads(external_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unresolved", 0, 0
    checked = confirmed = 0
    for number, innings in _all_innings(doc):
        score = expected[2].get(number)
        if score is None:
            continue
        checked += 1
        deliveries = [d for _, _, d in _iter_deliveries(innings)]
        total = sum(delivery_components(d)["total_runs"] for d in deliveries)
        total += sum(int(x or 0) for x in (innings.get("penalty_runs", {}) or {}).values())
        wickets = innings_wickets(innings)
        balls = sum(legal_delivery(d) for d in deliveries)
        if (total, wickets, f"{balls // 6}.{balls % 6}") == score:
            confirmed += 1
    return ("pass" if checked and confirmed == checked else "unresolved", checked, confirmed)


def _extras_scorecard_check(match_id: int, external_path: Path | None) -> tuple[int, int]:
    expected = SCORECARD_TYPED_EXTRAS.get(match_id, {})
    if not expected or not external_path or not external_path.is_file():
        return 0, 0
    try:
        doc = json.loads(external_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return len(expected), 0
    confirmed = 0
    for number, innings in _all_innings(doc):
        if number not in expected:
            continue
        amounts = {key: 0 for key in expected[number]}
        for _, _, delivery in _iter_deliveries(innings):
            extras = delivery.get("extras", {}) or {}
            for key in amounts:
                amounts[key] += int(extras.get(key, 0) or 0)
        if amounts == expected[number]:
            confirmed += 1
    return len(expected), confirmed


def assess_match(match: dict[str, str], player_rows: list[dict[str, str]], venue: dict[str, str] | None,
                 scoring_rows: list[dict[str, str]], selection: dict[str, str] | None) -> dict[str, Any]:
    mid = _int(match.get("official_match_id"))
    match_scoring = [r for r in scoring_rows if _int(r.get("match_id")) == mid]
    pcounts = Counter(r.get("status", "unresolved") for r in player_rows)
    venue_status = (venue or {}).get("status", "unresolved")
    downloaded = match.get("external_file_status") == "downloaded"
    match_exact = match.get("match_identity_status") == "exact" and all(
        _is_true(match.get(c)) for c in ("external_date_match", "external_teams_match", "external_format_match", "external_competition_family_match"))
    deliveries_aligned = downloaded and match.get("delivery_sequence_status") == "exact" and _int(match.get("aligned_deliveries")) == _int(match.get("external_delivery_rows")) == _int(match.get("official_local_delivery_rows")) and bool(match_scoring)
    batter_runs_exact = downloaded and bool(match_scoring) and all(r.get("batter_runs_match") == "exact" for r in match_scoring)
    ext_file = (match.get("external_filename") or "").strip()
    ext_path = ROOT / "data" / "external" / "cricsheet" / "pilot" / "matches" / ext_file if ext_file else None
    scorecard_status, scorecard_checked, scorecard_confirmed = _scorecard_check(mid, ext_path)
    extras_scorecard_checked, extras_scorecard_confirmed = _extras_scorecard_check(mid, ext_path)
    # The local source lacks per-delivery amounts/totals, so scorecard aggregate checks cannot clear these gates.
    gates = {
        "match_identity": _pass_or_unresolved(match_exact, downloaded),
        "venue_identity": "pass" if venue_status == "verified" else "unresolved",
        # Crosswalk 'verified' here is context/name evidence, not proven numeric-ID namespace equivalence.
        "player_identity": "pass" if downloaded and pcounts and pcounts.get("unresolved", 0) == 0 and pcounts.get("ambiguous", 0) == 0 and pcounts.get("candidate", 0) == 0 and match.get("player_identity_status") == "verified_namespace" else "unresolved",
        "delivery_alignment": "pass" if deliveries_aligned else "unresolved",
        "batter_runs": _pass_or_unresolved(batter_runs_exact, downloaded),
        "typed_extras": "unresolved",
        "delivery_totals": "unresolved",
        "legal_balls": "pass" if match.get("legal_balls_status") == "exact" and scorecard_status == "pass" else "unresolved",
        "wickets": "unresolved" if match.get("wickets_status") != "exact" else "pass",
        "innings_totals": scorecard_status,
        "targets": "unresolved",
        "match_result": "pass" if downloaded and match.get("result_status") == "exact" else "unresolved",
        # Bowler figures and bowler-credit wickets remain research-only/provisional, never silently promoted.
        "bowling_figures": "unresolved",
    }
    decision, rationale = decide_match(gates)
    file_hash = _sha(ext_path) if ext_path and ext_path.is_file() else ""
    source_url = (match.get("external_source_url") or "").strip()
    if not source_url and selection:
        source_url = selection.get("archive_url", "")
    license_text = selection.get("license", "") if selection else "Open Data Commons Attribution License 1.0 (ODC-BY 1.0) for Cricsheet files"
    blockers = [g for g in MANDATORY_GATES if gates[g] != "pass"]
    return {
        "official_match_id": mid, "competition": match.get("competition", ""), "format": match.get("format", ""),
        "season": match.get("season", ""), "match_date": match.get("match_date", ""), "home_team": match.get("home_team", ""),
        "away_team": match.get("away_team", ""), "pilot_role": match.get("pilot_role", ""),
        "external_file_status": match.get("external_file_status", ""), "external_match_id": Path(ext_file).stem if ext_file else "",
        "external_filename": ext_file, "external_archive_member": match.get("external_archive_member", ""),
        "source_url": source_url, "source_sha256": file_hash,
        "local_venue_id": match.get("venue_id", ""), "external_venue_name": match.get("external_external_venue", ""),
        "retrieved_utc": (selection or {}).get("retrieved_utc", ""), "license_attribution": license_text,
        "player_mapping_verified_context_count": pcounts.get("verified", 0), "player_mapping_candidate_count": pcounts.get("candidate", 0),
        "player_mapping_ambiguous_count": pcounts.get("ambiguous", 0), "player_mapping_unresolved_count": pcounts.get("unresolved", 0),
        "player_id_namespace_status": "unresolved", "venue_mapping_status": venue_status,
        **{f"gate_{k}": v for k, v in gates.items()}, "acceptance_status": decision,
        "blocking_checks": ";".join(blockers), "decision_rationale": rationale,
        "aligned_delivery_rows": _int(match.get("aligned_deliveries")),
        "independent_scorecard_innings_checked": scorecard_checked,
        "independent_scorecard_innings_confirmed": scorecard_confirmed,
        "independent_extras_scorecard_innings_checked": extras_scorecard_checked,
        "independent_extras_scorecard_innings_confirmed": extras_scorecard_confirmed,
    }


def generate(root: Path = ROOT) -> dict[str, int]:
    reports = root / "outputs" / "reports"
    matches = _read_csv(reports / "match_reconciliation.csv")
    player_rows = _read_csv(reports / "player_identity_crosswalk.csv")
    venue_rows = {str(_int(r.get("match_id"))): r for r in _read_csv(reports / "venue_identity_crosswalk.csv")}
    scoring_rows = _read_csv(reports / "scoring_extras_comparison.csv")
    selections = {str(_int(r.get("match_id"))): r for r in _read_csv(root / "data" / "external" / "cricsheet" / "pilot" / "pilot_selection_and_downloads.csv")}
    assessments = []
    registers = {r.get("file", ""): r for r in _read_csv(root / "data" / "external" / "cricsheet" / "pilot" / "register_manifest.csv")}
    people_manifest = registers.get("register/people.csv", {})
    venue_manifest = registers.get("register/venues.csv", {})
    official_match_hash = _sha(root / "data" / "raw" / "matches.csv")
    official_delivery_hash = _sha(root / "data" / "raw" / "ball_by_ball.csv")
    for m in matches:
        mid = str(_int(m.get("official_match_id")))
        assessed = assess_match(m, [p for p in player_rows if _int(p.get("match_id")) == _int(mid)], venue_rows.get(mid), scoring_rows, selections.get(mid))
        assessed.update({
            "official_matches_path": "data/raw/matches.csv", "official_matches_sha256": official_match_hash,
            "official_ball_by_ball_path": "data/raw/ball_by_ball.csv", "official_ball_by_ball_sha256": official_delivery_hash,
            "cricsheet_people_register_url": people_manifest.get("source_url", ""), "cricsheet_people_register_sha256": people_manifest.get("sha256", ""),
            "cricsheet_venues_register_url": venue_manifest.get("source_url", ""), "cricsheet_venues_register_sha256": venue_manifest.get("sha256", ""),
        })
        assessments.append(assessed)
    out = reports / "match_acceptance_status.csv"
    fields = list(dict.fromkeys(k for r in assessments for k in r))
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(assessments)

    # Isolated external layer: the header is retained even when no match passes the complete gate.
    accepted = {r["official_match_id"] for r in assessments if r["acceptance_status"] == "accepted"}
    data_rows = []
    assessment_by_id = {r["official_match_id"]: r for r in assessments}
    for r in scoring_rows:
        mid = _int(r.get("match_id"))
        if mid not in accepted:
            continue
        a = assessment_by_id[mid]
        data_rows.append({"official_match_id": mid, "external_match_id": a["external_match_id"], "innings": r["innings"], "over": r["over"], "delivery_position": r["delivery_position"],
            "batter_runs_external": r["batter_runs_external"], "extras_by_type_json": r["external_extras_by_type_json"], "extras_total_external": r["external_extras_total"], "total_runs_external": r["external_total_runs"],
            "legal_delivery_external": r["legal_external_candidate"], "wickets_json": r["wickets_json"], "source_provider": "Cricsheet", "source_url": a["source_url"], "source_filename": a["external_filename"],
            "source_sha256": a["source_sha256"], "license_attribution": a["license_attribution"], "acceptance_status": "accepted", "acceptance_reason": a["decision_rationale"]})
    gz_path = root / "data" / "processed" / "accepted_external_deliveries.csv.gz"
    gz_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(gz_path, "wt", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=ACCEPTED_COLUMNS); w.writeheader(); w.writerows(data_rows)

    counts = Counter(r["acceptance_status"] for r in assessments)
    _write_dictionary(reports / "accepted_data_dictionary.md")
    _write_report(reports / "match_acceptance_report.md", assessments, counts, len(data_rows))
    return {"matches": len(assessments), "accepted": counts["accepted"], "rejected": counts["rejected"], "unresolved": counts["unresolved"], "accepted_delivery_rows": len(data_rows)}


def _write_dictionary(path: Path) -> None:
    path.write_text('''# Accepted external delivery data dictionary

`data/processed/accepted_external_deliveries.csv.gz` is an external-only, gzip-compressed CSV. It contains **only deliveries from matches that pass every mandatory Phase 2E acceptance gate**. At the current assessment it has zero data rows and a header only; this is intentional. No candidate or unresolved values are exposed as accepted data.

| Field | Meaning |
|---|---|
| `official_match_id` | Local official fixture key; preserved as a distinct ID. |
| `external_match_id` | Cricsheet JSON member ID, not substituted for the local ID. |
| `innings`, `over`, `delivery_position` | External event coordinates; delivery position preserves illegal and repeated-ball events. |
| `batter_runs_external` | Cricsheet `runs.batter`. |
| `extras_by_type_json` | Explicit typed extras amounts from Cricsheet. |
| `extras_total_external` | Cricsheet `runs.extras`. |
| `total_runs_external` | Cricsheet `runs.total`. |
| `legal_delivery_external` | Derived from typed wides/no-balls under the validated event rule. |
| `wickets_json` | Raw dismissal event details; team wickets and bowler-credit wickets remain distinct. |
| `source_provider`, `source_url`, `source_filename`, `source_sha256` | Provider provenance and exact source artifact identity. |
| `license_attribution` | Required source license/attribution. |
| `acceptance_status`, `acceptance_reason` | Match gate result and audit rationale. |

Bowler-conceded runs and bowler-credit wickets are not present as accepted player-level metrics in this schema. They remain provisional until independently verified and player IDs are authoritatively crosswalked. Original official CSVs are never modified by this layer.
''', encoding="utf-8")


def _write_report(path: Path, rows: list[dict[str, Any]], counts: Counter, accepted_rows: int) -> None:
    gates = ["match_identity", "venue_identity", "player_identity", "delivery_alignment", "batter_runs", "typed_extras", "delivery_totals", "legal_balls", "wickets", "innings_totals", "targets", "match_result", "bowling_figures"]
    gate_stats = {g: Counter(r[f"gate_{g}"] for r in rows) for g in gates}
    batter_rows_checked = sum(_int(r.get("aligned_delivery_rows")) for r in rows if r.get("gate_batter_runs") == "pass")
    scorecard_innings_checked = sum(_int(r.get("independent_scorecard_innings_checked")) for r in rows)
    scorecard_innings_confirmed = sum(_int(r.get("independent_scorecard_innings_confirmed")) for r in rows)
    extras_innings_checked = sum(_int(r.get("independent_extras_scorecard_innings_checked")) for r in rows)
    extras_innings_confirmed = sum(_int(r.get("independent_extras_scorecard_innings_confirmed")) for r in rows)
    lines = ["# Phase 2F.6 — Reconciliation integration and match acceptance", "", "## Decision summary", "",
        f"The pilot contains **{len(rows)} matches**: **{counts['accepted']} accepted**, **{counts['rejected']} rejected**, and **{counts['unresolved']} unresolved**.",
        f"The isolated accepted-data layer contains **{accepted_rows} delivery rows**. Because no match passes every mandatory gate, it contains only its schema header. Supplemental reliable metric coverage gained from accepted Cricsheet data is **0 matches and 0 deliveries**.",
        "", "The assessment applies the existing Phase 2E zero-unexplained-difference rule. A check passes only with verified evidence. Missing sources, candidate mappings, ambiguous mappings, and unresolved field semantics remain unresolved. No gate was lowered.", "",
        "## Mandatory gate outcomes", "", "| Gate | Pass | Unresolved | Fail |", "|---|---:|---:|---:|"]
    for g in gates:
        s = gate_stats[g]; lines.append(f"| {g.replace('_', ' ')} | {s['pass']} | {s['unresolved']} | {s['fail']} |")
    lines += ["", "Diagnostic evidence coverage, separate from accepted-data coverage: batter-run comparisons exact on **" + str(batter_rows_checked) + " delivery rows**; independently checked score/overs/wicket totals **" + str(scorecard_innings_confirmed) + "/" + str(scorecard_innings_checked) + " innings**; typed extras against detailed scorecards **" + str(extras_innings_confirmed) + "/" + str(extras_innings_checked) + " innings**. These validation results do not override other mandatory gates.", "", "## Integrated findings", "",
        "- **Identity:** player crosswalk statuses (`verified`, `candidate`, `ambiguous`, `unresolved`) are preserved as separate counts in the CSV. The Phase 2F.4 ‘verified’ label establishes exact match/team/competition name context only; it does not prove that local numeric IDs and Cricsheet IDs share a namespace. The player ID gate therefore remains unresolved for every control. Candidate venue aliases are not promoted; only match 40725 has a verified venue link, and that alone cannot clear the full gate.",
        "- **Scoring:** Phase 2F.5 verified Cricsheet event arithmetic and independently checked innings scorecards, including typed-extra totals for 8 detailed innings. This does not supply the official feed’s missing per-delivery total runs or extras amounts. Those mandatory comparisons remain unresolved. Match 20182 also retains two category-label disagreements; no assumption resolves them.",
        "- **Legal balls/wickets:** external typed wide/no-ball rules reproduce scorecard over notation, but local `Overstep`/unknown-event semantics and wicket/player attribution do not pass the event-level acceptance gate for every control. Retired hurt is excluded from wickets lost under the corrected comparator; that fix did not clear other gates.",
        "- **Bowling:** bowler-conceded runs are independently corroborated only at aggregate innings level for 34429 and 40725. Player-level attribution is blocked by unresolved ID mapping. Bowler-credit wickets remain separate from team wickets and provisional; no bowler figures are exported as accepted.",
        "- **Missing-delivery candidates:** all 16 no-local-row matches remain unresolved because no Cricsheet delivery JSON was downloaded/uniquely established. No records were fabricated or exported.",
        "", "## Match-by-match audit", "", "| Match | Status | Venue | Player IDs | Scoring | Main reason |", "|---:|---|---|---|---|---|"]
    for r in rows:
        score_state = "pass" if all(r[f"gate_{x}"] == "pass" for x in ("batter_runs", "typed_extras", "delivery_totals", "legal_balls", "wickets", "innings_totals", "targets")) else "incomplete"
        main = r["decision_rationale"].replace("mandatory checks lack verified evidence: ", "")
        if len(main) > 150: main = main[:147] + "..."
        lines.append(f"| {r['official_match_id']} | {r['acceptance_status']} | {r['venue_mapping_status']} | {r['player_id_namespace_status']} | {score_state} | {main} |")
    lines += ["", "## Provenance and immutable inputs", "",
        "For each downloaded control, `match_acceptance_status.csv` records Cricsheet archive URL, JSON member ID, SHA-256, retrieval time, ODC-BY 1.0 attribution, match key and scorecard coverage. Cricsheet originals remain under `data/external/cricsheet/pilot/matches/`; attribution is preserved in `data/external/cricsheet/pilot/ATTRIBUTION.txt`. The local official CSVs and original reconciliation outputs were not overwritten.",
        "", "## Reproduction", "", "```powershell", ".\\venv\\Scripts\\python.exe -m src.match_acceptance", ".\\venv\\Scripts\\python.exe -m pytest -q tests", ".\\venv\\Scripts\\python.exe -m compileall -q src tests", "```", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    print(json.dumps(generate(), indent=2))
