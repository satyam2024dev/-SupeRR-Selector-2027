"""Phase 3E provider intake validation.

Provider data is read-only and remains outside ``data/raw``. This module validates
the provider's declared schema and delivery sample; it never repairs or merges data.
All example fixtures used by tests are synthetic.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "outputs" / "reports"

# Fields required to validate an event's score, state, identity, and provenance.
EXPECTED_FIELDS: dict[str, dict[str, str]] = {
    "official_match_id": {"type": "string", "nullable": "false", "definition": "Reviewed local match key; must be supported by a provider crosswalk, never names/date alone."},
    "provider_match_id": {"type": "string", "nullable": "false", "definition": "Stable provider match identifier."},
    "innings": {"type": "integer", "nullable": "false", "definition": "Provider innings number; Super Overs separately identified."},
    "innings_type": {"type": "string", "nullable": "false", "definition": "regular or super_over; dictionary must define other values."},
    "sequence": {"type": "integer", "nullable": "false", "definition": "Stable event sequence within match innings, including illegal deliveries."},
    "over": {"type": "integer", "nullable": "false", "definition": "Provider over index with documented origin/convention."},
    "delivery_position": {"type": "integer", "nullable": "false", "definition": "Provider event position; repeated labels for illegal events are permitted."},
    "batter_id": {"type": "string", "nullable": "false", "definition": "Stable provider player ID for striker."},
    "non_striker_id": {"type": "string", "nullable": "false", "definition": "Stable provider player ID for non-striker."},
    "bowler_id": {"type": "string", "nullable": "false", "definition": "Stable provider player ID for bowler."},
    "batter_runs": {"type": "integer", "nullable": "false", "definition": "Runs credited to striker on event."},
    "wides_runs": {"type": "integer", "nullable": "false", "definition": "Wide-extra amount on event, zero when absent."},
    "noballs_runs": {"type": "integer", "nullable": "false", "definition": "No-ball-extra amount on event, zero when absent."},
    "byes_runs": {"type": "integer", "nullable": "false", "definition": "Bye amount on event, zero when absent."},
    "legbyes_runs": {"type": "integer", "nullable": "false", "definition": "Leg-bye amount on event, zero when absent."},
    "penalty_runs": {"type": "integer", "nullable": "false", "definition": "Penalty amount attributed to this event, zero when absent."},
    "other_extras_runs": {"type": "integer", "nullable": "false", "definition": "Other typed extras amount, with type in dictionary."},
    "total_runs": {"type": "integer", "nullable": "false", "definition": "Total team runs added on event; invariant is batter_runs plus typed extras."},
    "is_legal_delivery": {"type": "boolean", "nullable": "false", "definition": "Provider's explicit legal-ball result under documented rules."},
    "is_wicket": {"type": "boolean", "nullable": "false", "definition": "Dismissal event indicator; semantics must distinguish retirement events."},
    "team_wicket_lost": {"type": "boolean", "nullable": "false", "definition": "Whether event adds one to innings wickets lost."},
    "bowler_credited_wicket": {"type": "boolean", "nullable": "false", "definition": "Whether dismissal is credited to bowler under documented rules."},
    "dismissal_type": {"type": "string", "nullable": "true", "definition": "Provider dismissal code/label; dictionary must define team-wicket and bowler-credit effects."},
    "dismissed_player_id": {"type": "string", "nullable": "true", "definition": "Provider player ID for dismissed/retired player, if applicable."},
    "target_runs": {"type": "integer", "nullable": "true", "definition": "Runs needed to win for this innings, explicitly supplied per event or documented innings value."},
    "target_balls": {"type": "integer", "nullable": "true", "definition": "Legal-ball allowance for chase; DLS/revised allowance semantics documented."},
    "revised_target": {"type": "boolean", "nullable": "false", "definition": "Whether target/allowance is revised; dictionary defines DLS/par fields."},
    "scheduled_legal_balls": {"type": "integer", "nullable": "true", "definition": "Innings legal-ball allowance, including revisions where applicable."},
    "innings_total_runs": {"type": "integer", "nullable": "true", "definition": "Scorecard total for this innings, for endpoint reconciliation only."},
    "innings_wickets": {"type": "integer", "nullable": "true", "definition": "Scorecard wickets lost for this innings."},
    "is_super_over": {"type": "boolean", "nullable": "false", "definition": "Explicit Super Over indicator, consistent with innings_type."},
}

DICT_COLUMNS = {"field_name", "type", "definition", "nullable", "units", "grain", "enum_values"}
DELIVERY_KEY = ["official_match_id", "innings", "sequence"]
EXTRA_FIELDS = ["wides_runs", "noballs_runs", "byes_runs", "legbyes_runs", "penalty_runs", "other_extras_runs"]
NONNEGATIVE_FIELDS = ["batter_runs", *EXTRA_FIELDS, "total_runs", "target_runs", "target_balls", "scheduled_legal_balls", "innings_total_runs", "innings_wickets", "over", "delivery_position", "sequence", "innings"]


def _decision(field: str, status: str, evidence: str, n: int = 0) -> dict[str, Any]:
    return {"field": field, "status": status, "rows_checked": n, "evidence": evidence}


def validate_dictionary(dictionary: pd.DataFrame) -> list[dict[str, Any]]:
    """Check that the provider data dictionary declares required semantics."""
    out = []
    missing_cols = DICT_COLUMNS - set(dictionary.columns)
    if missing_cols:
        return [_decision("data_dictionary", "fail", f"Missing dictionary columns: {sorted(missing_cols)}")]
    if dictionary.field_name.duplicated().any():
        out.append(_decision("data_dictionary", "fail", "Duplicate field_name entries."))
    indexed = dictionary.set_index("field_name", drop=False)
    for field, spec in EXPECTED_FIELDS.items():
        if field not in indexed.index:
            out.append(_decision(field, "unresolved", "Field absent from provider dictionary."))
            continue
        row = indexed.loc[field]
        if isinstance(row, pd.DataFrame):
            out.append(_decision(field, "fail", "Field has duplicate dictionary definitions."))
            continue
        declared_type = str(row["type"]).strip().lower()
        declared_nullable = str(row["nullable"]).strip().lower()
        definition = str(row["definition"]).strip()
        if declared_type != spec["type"] or declared_nullable != spec["nullable"]:
            out.append(_decision(field, "fail", f"Declared type/nullable {declared_type}/{declared_nullable}; expected {spec['type']}/{spec['nullable']}."))
        elif not definition or definition.lower() in {"nan", "none"}:
            out.append(_decision(field, "unresolved", "Field present but definition is blank."))
        else:
            out.append(_decision(field, "pass", "Field, type, nullability and nonblank definition declared."))
    return out


def validate_deliveries(deliveries: pd.DataFrame) -> list[dict[str, Any]]:
    """Validate sample records without filling missing values or coercing semantics."""
    deliveries = deliveries.copy()
    n = len(deliveries)
    missing = set(EXPECTED_FIELDS) - set(deliveries.columns)
    checks: list[dict[str, Any]] = []
    for col, spec in EXPECTED_FIELDS.items():
        if col not in deliveries:
            checks.append(_decision(col, "unresolved", "Column not supplied in sample file.", n))
            continue
        null_count = int(deliveries[col].isna().sum())
        if spec["nullable"] == "false" and null_count:
            checks.append(_decision(col, "fail", f"Required field has {null_count} null value(s).", n))
            continue
        typ = spec["type"]
        values = deliveries[col].dropna()
        valid = True
        if typ == "integer":
            valid = values.map(lambda x: isinstance(x, (int,)) or (isinstance(x, float) and x.is_integer())).all()
        elif typ == "boolean":
            valid = values.map(lambda x: isinstance(x, bool) or str(x).strip().lower() in {"true", "false"}).all()
        elif typ == "string":
            valid = values.map(lambda x: isinstance(x, str) and bool(x.strip())).all()
        checks.append(_decision(col, "pass" if valid else "fail", "Observed values match declared scalar type." if valid else f"Values do not conform to expected {typ} type.", n))

    for col, spec in EXPECTED_FIELDS.items():
        if col not in deliveries:
            continue
        if spec["type"] == "integer":
            deliveries[col] = pd.to_numeric(deliveries[col].replace("", pd.NA), errors="coerce")
        elif spec["type"] == "boolean":
            deliveries[col] = deliveries[col].map(lambda x: x if isinstance(x, bool) else (True if str(x).strip().lower() == "true" else (False if str(x).strip().lower() == "false" else pd.NA)))

    if not missing:
        duplicate = deliveries.duplicated(DELIVERY_KEY, keep=False)
        checks.append(_decision("delivery_key", "fail" if duplicate.any() else "pass", f"{int(duplicate.sum())} rows participate in duplicate match/innings/sequence keys.", n))
        nonnegative_bad = {c: int((pd.to_numeric(deliveries[c], errors="coerce") < 0).sum()) for c in NONNEGATIVE_FIELDS if c in deliveries}
        bad = {c: count for c, count in nonnegative_bad.items() if count}
        checks.append(_decision("nonnegative_amounts", "fail" if bad else "pass", f"Negative values by field: {bad or 'none'}.", n))

        total_known = deliveries[["batter_runs", *EXTRA_FIELDS, "total_runs"]].notna().all(axis=1)
        calc = deliveries["batter_runs"] + deliveries[EXTRA_FIELDS].sum(axis=1)
        disagree = total_known & (calc != deliveries.total_runs)
        total_status = "fail" if disagree.any() else ("unresolved" if not total_known.all() else "pass")
        checks.append(_decision("total_runs", total_status, f"{int(total_known.sum())}/{n} rows have complete components; {int(disagree.sum())} violate batter + typed extras = total.", n))

        wide = deliveries.wides_runs.fillna(0).gt(0)
        noball = deliveries.noballs_runs.fillna(0).gt(0)
        legal = deliveries.is_legal_delivery.fillna(False)
        contradictory = (wide | noball) & legal
        checks.append(_decision("legal_ball_semantics", "fail" if contradictory.any() else "pass", f"{int(contradictory.sum())} wide/no-ball events marked legal; byes/leg-byes are not treated as illegal by this check.", n))
        super_flag = deliveries.is_super_over.fillna(False)
        super_conflict = (super_flag & deliveries.innings_type.ne("super_over")) | (~super_flag & deliveries.innings_type.eq("super_over"))
        checks.append(_decision("super_over", "fail" if super_conflict.any() else "pass", f"{int(super_conflict.sum())} conflicts between is_super_over and innings_type.", n))
        team_wicket = deliveries.team_wicket_lost.fillna(False)
        wicket_bad = team_wicket & (~deliveries.is_wicket.fillna(False) | deliveries.dismissal_type.isna() | deliveries.dismissed_player_id.isna())
        credit_bad = deliveries.bowler_credited_wicket.fillna(False) & ~team_wicket
        checks.append(_decision("wicket_semantics", "fail" if (wicket_bad | credit_bad).any() else "pass", f"{int(wicket_bad.sum())} team-wicket rows lack dismissal evidence or is_wicket; {int(credit_bad.sum())} bowler-credit rows are not team wickets.", n))
        chase = deliveries.innings.eq(2) & ~super_flag
        target_missing = chase & (deliveries.target_runs.isna() | deliveries.target_balls.isna())
        target_invalid = chase & ((deliveries.target_runs.fillna(0) <= 0) | (deliveries.target_balls.fillna(0) <= 0))
        checks.append(_decision("targets", "unresolved" if target_missing.any() else ("fail" if target_invalid.any() else "pass"), f"{int(target_missing.sum())} regular-chase rows lack target runs/balls; {int(target_invalid.sum())} have nonpositive values.", n))
        player_ids = deliveries[["batter_id", "non_striker_id", "bowler_id"]]
        player_missing = player_ids.isna() | player_ids.astype(str).apply(lambda column: column.str.strip().eq(""))
        checks.append(_decision("player_ids", "fail" if player_missing.any(axis=None) else "pass", "Stable provider IDs are present for batter, non-striker and bowler." if not player_missing.any(axis=None) else "One or more required provider player IDs are missing.", n))
        strata = {
            "ordinary": deliveries[EXTRA_FIELDS].fillna(0).eq(0).all(axis=1) & deliveries.batter_runs.ge(0),
            "wides": deliveries.wides_runs.gt(0),
            "no_balls": deliveries.noballs_runs.gt(0),
            "byes": deliveries.byes_runs.gt(0),
            "legbyes": deliveries.legbyes_runs.gt(0),
            "penalties": deliveries.penalty_runs.gt(0),
            "other_extras": deliveries.other_extras_runs.gt(0),
            "wickets": deliveries.is_wicket,
            "super_overs": super_flag,
            "revised_targets": deliveries.revised_target.fillna(False),
        }
        for name, mask in strata.items():
            count = int(mask.fillna(False).sum())
            checks.append(_decision(f"stratum_{name}", "unresolved" if count == 0 else "pass", f"{count} sample events in requested stratum; presence only, with row-level rules checked above.", n))
    else:
        checks.append(_decision("delivery_semantics", "unresolved", f"Cross-field validation requires missing columns: {sorted(missing)}.", n))
    return checks


def compare_official(deliveries: pd.DataFrame, official: pd.DataFrame) -> list[dict[str, Any]]:
    """Compare only exact, key-aligned fields that the official source actually supports."""
    required_official = {"match_id", "innings", "overid", "over_ball_num", "runs"}
    if not required_official.issubset(official.columns):
        return [_decision("official_comparison", "unresolved", f"Official rows lack columns: {sorted(required_official - set(official.columns))}")]
    if "official_match_id" not in deliveries or "innings" not in deliveries or "over" not in deliveries or "delivery_position" not in deliveries:
        return [_decision("official_comparison", "unresolved", "Provider lacks reviewed match key/event-coordinate fields.")]
    # The innings/over/event coordinate alignment must be an explicit provider mapping.
    if not deliveries.attrs.get("official_coordinate_mapping_verified", False):
        return [_decision("official_comparison", "unresolved", "Coordinate mapping is not declared as reviewed; no date/name-only join attempted.")]
    left_keys, right_keys = deliveries.copy(), official.copy()
    left_keys["official_match_id"] = left_keys.official_match_id.astype(str)
    right_keys["match_id"] = right_keys.match_id.astype(str)
    left = left_keys.merge(right_keys, left_on=["official_match_id", "innings", "over", "delivery_position"], right_on=["match_id", "innings", "overid", "over_ball_num"], how="left", suffixes=("_provider", "_official"), indicator=True)
    matched = left._merge.eq("both")
    # `runs` in the official file is not assumed to be total team runs. Compare to batter_runs only.
    compared = matched & left.batter_runs.notna() & left.runs.notna()
    diff = compared & left.batter_runs.ne(left.runs)
    out = [_decision("official_batter_runs", "unresolved" if not compared.any() else ("fail" if diff.any() else "pass"), f"{int(compared.sum())} exact-coordinate values compared; {int(diff.sum())} differ; official runs is compared only to declared batter_runs." , len(left))]
    out.append(_decision("official_team_total", "unresolved", "Official ball_by_ball.csv has no per-event team total; never compare provider total_runs to official runs." , len(left)))
    out.append(_decision("official_player_ids", "unresolved", "No verified player-ID namespace crosswalk supplied to this validator." , len(left)))
    return out


def pressure_coverage_gate(field_checks: list[dict[str, Any]], dictionary_checks: list[dict[str, Any]], *, semantic_review_passed: bool = False) -> dict[str, Any]:
    """Return a blocked status unless all state prerequisites pass both audits."""
    required = {"total_runs", "legal_ball_semantics", "targets", "super_over", "stratum_ordinary",
                "stratum_wides", "stratum_no_balls", "stratum_byes", "stratum_legbyes",
                "stratum_penalties", "stratum_other_extras", "stratum_wickets", "stratum_super_overs", "stratum_revised_targets"}
    statuses = {c["field"]: c["status"] for c in [*field_checks, *dictionary_checks]}
    blocked = sorted(name for name in required if statuses.get(name) != "pass")
    if not semantic_review_passed:
        blocked.append("independent_semantic_review")
    return {"status": "blocked_unresolved" if blocked else "eligible_to_estimate", "coverage_rows": None if blocked else "requires complete source-backed delivery replay", "blocked_checks": blocked, "note": "No sample-size or pressure coverage estimate is inferred from incomplete or synthetic records."}


def validate_bundle(bundle: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Read a versioned response bundle: manifest.json, data_dictionary.csv, deliveries.csv."""
    manifest_path, dict_path, delivery_path = bundle / "manifest.json", bundle / "data_dictionary.csv", bundle / "deliveries.csv"
    if not manifest_path.exists():
        checks = [_decision("manifest", "unresolved", "No provider response manifest supplied.")]
        return pd.DataFrame(checks), {"status": "blocked_unresolved", "coverage_rows": None, "blocked_checks": ["manifest"], "note": "No provider response files received."}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = str(manifest.get("schema_version", "")).strip()
    base = [_decision("manifest", "pass" if version else "fail", f"schema_version={version or 'missing'}; provider={manifest.get('provider', 'unspecified')}.")]
    if not dict_path.exists():
        base.append(_decision("data_dictionary", "unresolved", "data_dictionary.csv not supplied."))
        dict_checks = [_decision("data_dictionary", "unresolved", "Dictionary file missing.")]
    else:
        dict_checks = validate_dictionary(pd.read_csv(dict_path, dtype=str, keep_default_na=False))
    if not delivery_path.exists():
        delivery_checks = [_decision("deliveries", "unresolved", "deliveries.csv not supplied.")]
        deliveries = None
    else:
        deliveries = pd.read_csv(delivery_path, keep_default_na=False)
        delivery_checks = validate_deliveries(deliveries)
    combined = [*base, *dict_checks, *delivery_checks]
    semantic_review_path = bundle / "semantic_review.csv"
    semantic_review_passed = False
    if semantic_review_path.exists():
        review = pd.read_csv(semantic_review_path, dtype=str, keep_default_na=False)
        needed = {"field_name", "status", "evidence", "reviewer", "review_date"}
        if needed.issubset(review.columns):
            state_fields = {"total_runs", "is_legal_delivery", "target_runs", "target_balls", "scheduled_legal_balls", "innings_type", "is_super_over", "team_wicket_lost"}
            selected = review[review.field_name.isin(state_fields)]
            reviewed = set(selected.loc[selected.status.eq("pass") & selected.evidence.str.strip().ne("") & selected.reviewer.str.strip().ne("") & selected.review_date.str.strip().ne(""), "field_name"])
            semantic_review_passed = state_fields.issubset(reviewed)
            combined.append(_decision("independent_semantic_review", "pass" if semantic_review_passed else "unresolved", f"{len(reviewed)}/{len(state_fields)} state-critical definitions have named reviewer, date and evidence."))
        else:
            combined.append(_decision("independent_semantic_review", "unresolved", f"semantic_review.csv requires columns {sorted(needed)}."))
    else:
        combined.append(_decision("independent_semantic_review", "unresolved", "Internal reviewed semantic_review.csv is absent; nonblank provider definitions alone do not establish correctness."))
    crosswalk_path, coordinate_path = bundle / "match_crosswalk.csv", bundle / "coordinate_review.csv"
    coordinate_verified = False
    if coordinate_path.exists():
        coordinate_review = pd.read_csv(coordinate_path, dtype=str, keep_default_na=False)
        coordinate_verified = {"status", "evidence", "reviewer"}.issubset(coordinate_review.columns) and len(coordinate_review) > 0 and coordinate_review.status.eq("verified").all() and coordinate_review.evidence.str.strip().ne("").all() and coordinate_review.reviewer.str.strip().ne("").all()
    match_verified = False
    if crosswalk_path.exists():
        match_crosswalk = pd.read_csv(crosswalk_path, dtype=str, keep_default_na=False)
        match_verified = {"provider_match_id", "official_match_id", "status", "evidence"}.issubset(match_crosswalk.columns) and len(match_crosswalk) > 0 and match_crosswalk.status.eq("verified").all() and match_crosswalk.evidence.str.strip().ne("").all()
    if deliveries is not None and (ROOT / "data" / "raw" / "ball_by_ball.csv").exists() and coordinate_verified and match_verified:
        deliveries.attrs["official_coordinate_mapping_verified"] = True
        official = pd.read_csv(ROOT / "data" / "raw" / "ball_by_ball.csv", low_memory=False)
        combined.extend(compare_official(deliveries, official))
    else:
        combined.append(_decision("official_comparison", "unresolved", "Requires provider delivery data plus verified match_crosswalk.csv and internal coordinate_review.csv; no date/name-only alignment is attempted."))
    gate = pressure_coverage_gate(delivery_checks, dict_checks, semantic_review_passed=semantic_review_passed)
    gate["schema_version"] = version or None
    gate["manifest"] = manifest
    return pd.DataFrame(combined), gate


def write_bundle_validation(bundle: Path, output_dir: Path) -> dict[str, Any]:
    """Validate a provider bundle and write only audit outputs to ``output_dir``.

    The bundle is read-only input. This function does not write accepted data,
    alter match decisions, or copy provider rows into project analysis files.
    """
    bundle_resolved = bundle.resolve()
    output_resolved = output_dir.resolve()
    protected_dirs = [bundle_resolved, (ROOT / "data" / "raw").resolve(), (ROOT / "data" / "processed").resolve()]
    if any(output_resolved == protected or protected in output_resolved.parents for protected in protected_dirs):
        raise ValueError("Validation output must be outside the provider bundle, data/raw, and data/processed.")
    checks, gate = validate_bundle(bundle_resolved)
    output_resolved.mkdir(parents=True, exist_ok=True)
    checks.to_csv(output_resolved / "provider_response_field_checks.csv", index=False)
    (output_resolved / "provider_response_validation_spec.md").write_text(_spec(gate), encoding="utf-8")
    (output_resolved / "provider_response_gate.json").write_text(json.dumps(gate, indent=2, default=str), encoding="utf-8")
    return gate


def write_current_reports() -> None:
    """Emit framework outputs; absent provider response is explicitly unresolved."""
    REPORTS.mkdir(parents=True, exist_ok=True)
    bundle = ROOT / "data" / "external" / "provider_response" / "current"
    if bundle.exists():
        checks, gate = validate_bundle(bundle)
    else:
        checks = pd.DataFrame([_decision(f, "unresolved", "No provider response bundle received; no real provider values assessed.") for f in ["manifest", "data_dictionary", "deliveries", *EXPECTED_FIELDS.keys(), "official_comparison"]])
        gate = {"status": "blocked_unresolved", "coverage_rows": None, "blocked_checks": ["no_provider_response"], "note": "Potential pressure-state coverage is not estimated until real fields pass validation."}
    checks.to_csv(REPORTS / "provider_response_field_checks.csv", index=False)
    test_cases = [
        ("SYN-01", "complete typed dictionary + ordinary event", "pass", "Synthetic only"),
        ("SYN-02", "missing required dictionary field", "unresolved", "Synthetic only"),
        ("SYN-03", "declared type differs from expected type", "fail", "Synthetic only"),
        ("SYN-04", "required delivery value null", "fail", "Synthetic only"),
        ("SYN-05", "batter + typed extras equals total", "pass", "Synthetic only"),
        ("SYN-06", "delivery total differs from component sum", "fail", "Synthetic only"),
        ("SYN-07", "wide marked legal", "fail", "Synthetic only"),
        ("SYN-08", "no-ball marked legal", "fail", "Synthetic only"),
        ("SYN-09", "bye or leg-bye on legal event", "pass", "Synthetic only"),
        ("SYN-10", "regular chase target absent", "unresolved", "Synthetic only"),
        ("SYN-11", "duplicate event key", "fail", "Synthetic only"),
        ("SYN-12", "provider player ID absent", "fail", "Synthetic only"),
        ("SYN-13", "retired hurt not a team wicket", "pass", "Synthetic only"),
        ("SYN-14", "retired out is a team wicket", "pass", "Synthetic only"),
        ("SYN-15", "ordinary dismissal with team wicket", "pass", "Synthetic only"),
        ("SYN-16", "Super Over has explicit separate innings identity", "pass", "Synthetic only"),
        ("SYN-17", "revised target and legal-ball allowance declared", "pass", "Synthetic only"),
        ("SYN-18", "provider total cannot compare to official runs column", "unresolved", "Synthetic only"),
        ("SYN-19", "pressure coverage gate fails when target semantics unresolved", "blocked_unresolved", "Synthetic only"),
        ("SYN-20", "all state fields pass; replay still needs complete real innings", "eligible_to_estimate", "Synthetic only; no pressure estimate produced"),
        ("SYN-21", "penalty extras component and category", "pass", "Synthetic only"),
        ("SYN-22", "other extras component and category", "pass", "Synthetic only"),
    ]
    pd.DataFrame(test_cases, columns=["case_id", "scenario", "expected_decision", "fixture_status"]).to_csv(REPORTS / "provider_response_test_cases.csv", index=False)
    pd.DataFrame([{"field_name": k, **v, "grain": "delivery or innings as stated in definition", "units": "runs/balls/identifier/boolean as applicable", "enum_values": "provider must document"} for k, v in EXPECTED_FIELDS.items()]).to_csv(REPORTS / "provider_response_expected_schema.csv", index=False)
    (REPORTS / "provider_response_validation_spec.md").write_text(_spec(gate), encoding="utf-8")


def _spec(gate: dict[str, Any]) -> str:
    fields = "\n".join(f"- `{field}` — {spec['type']}, nullable `{spec['nullable']}`: {spec['definition']}" for field, spec in EXPECTED_FIELDS.items())
    return f"""# Phase 3E — Provider response validation specification

## Intake status

Current response status: **{gate['status']}**. No real provider values are represented by synthetic test cases. Coverage rows: **not estimated**. The framework does not fill missing fields, overwrite official files, modify match acceptance, or change pressure definitions/evidence floors.

## Required bundle and versioning

Place a read-only provider package at `data/external/provider_response/<release>/` with `manifest.json`, `data_dictionary.csv`, `deliveries.csv`, `innings_summary.csv`, `match_crosswalk.csv`, `player_register.csv`, and `player_crosswalk.csv`; include referenced independent scorecards/source records. Keep originals untouched. The project maintains internal `semantic_review.csv` and `coordinate_review.csv`; these are review artifacts, not provider deliverables. Manifest must identify provider/product, schema and release version, effective dates, license/attribution, source artifact names/hashes, and crosswalk provenance. A match ID mapping must not be derived from date/team names alone.

The dictionary CSV columns are `field_name,type,definition,nullable,units,grain,enum_values`; every required field below needs a nonblank definition and exact expected scalar type/nullability. A nonblank definition is only a declaration, not proof its meaning is correct. Before state coverage can be estimated, a separate internal `semantic_review.csv` must document a named reviewer, review date, evidence and pass decision for every state-critical concept. Extra provider fields are retained but not required by this validator.

## Expected delivery fields

{fields}

`innings_summary.csv` must carry `official_match_id,provider_match_id,innings,innings_type,innings_total_runs,innings_wickets,innings_legal_balls,innings_status,target_runs,target_balls,revised_target,scorecard_source_url`. It supplies endpoint reconciliation, not a substitute for per-delivery state. `match_crosswalk.csv` must map provider match IDs to the official match IDs using date, competition, both teams, venue and available identifiers, with evidence/source and decision; unresolved matches stay unmapped. `player_register.csv` must identify the provider namespace and stable IDs with roster/team/date context; `player_crosswalk.csv` maps those IDs to official IDs only where independently reviewed, with decision and evidence. Candidate mappings are not accepted comparisons.

## Validation gates

1. Manifest, schema version and dictionary: version present; required concepts and exact types/nullability documented. Missing field is unresolved; contradiction is fail.
2. Delivery shape and missingness: stable `(official_match_id, innings, sequence)` key unique; required identifiers and values non-null; numeric run/ball quantities are nonnegative integers; booleans are explicit.
3. Scoring: `total_runs = batter_runs + wides_runs + noballs_runs + byes_runs + legbyes_runs + penalty_runs + other_extras_runs` for every complete event. Missing component is unresolved; unequal total fails. Provider must document extra-type enum, combination precedence, penalty scope and whether penalty runs occur off-event.
4. Legal balls: explicit `is_legal_delivery`; any positive wide/no-ball amount marked legal fails. Byes/leg-byes alone do not fail legality. Other/Penalty/Overstep behavior remains unresolved until provider definitions and stratified real examples establish semantics; do not infer an indicator from labels.
5. Wickets: retain `is_wicket`, `team_wicket_lost`, and `bowler_credited_wicket` separately. Definitions must distinguish retired hurt/out, ordinary dismissals, no-ball exceptions, and non-bowler-credit dismissals. A team wicket requires explicit dismissal/player evidence; bowler credit cannot exceed team wicket loss.
6. Targets and unusual innings: regular chase rows need positive target runs and legal-ball allowance; revised targets require DLS/par method and effective target/allowance provenance. Super Overs are explicitly tagged and isolated. Incomplete/abandoned innings need status and endpoint details. Duplicate/missing sequence keys fail or remain unresolved as applicable.
7. Official comparison: compare only after an explicit reviewed `match_crosswalk.csv` and internal `coordinate_review.csv` with verified status/evidence/reviewer. Existing official `runs` is compared only to provider `batter_runs` where that field's documented semantics support it; it is not a team-run total. Official source does not contain per-event total runs, so that comparison remains unresolved. Player IDs remain unresolved without a verified namespace crosswalk. No values are copied into official records.
8. Semantic review and coverage: human review of the provider definitions against complete stratified examples is required and recorded in internal `semantic_review.csv`; a provider-authored definition is not self-validating. Pressure-state replay is permitted only after per-delivery totals, legal-ball semantics, targets/allowances, Super Over and event-sequence checks pass, with complete innings and match identity. A passed sample schema alone is not coverage. Actual pressure/baseline rows require a source-backed complete real delivery set and existing approved classifier; the validator does not compute player scores or ranks.

## Stratified test obligations

The provider sample must include ordinary deliveries, wides, no-balls/Overstep, byes, leg-byes, each wicket/dismissal class, Super Overs, revised-target/DLS events, and any Other/Penalty/combined extras. Every stratum should include complete innings packages and scorecard endpoints. `provider_response_test_cases.csv` records expected synthetic cases; they are explicitly not provider evidence.

## Field decision meanings

- **pass**: supplied and validated against the defined field-level checks on the rows shown.
- **fail**: observed contradiction, malformed type/value, duplicate key, or invariant violation.
- **unresolved**: absent field, missing definition, unavailable independent comparator, or inadequate sample/evidence.

For the current workspace: {gate.get('note', 'No provider response supplied.')}

## Provider must supply

- Versioned `manifest.json` with provider/release/schema identifiers, effective date, license/attribution, hashes, and provenance.
- `data_dictionary.csv` with all required field definitions and null/units/enum/grain semantics (the project maintains a separate reviewed semantic decision file).
- Complete `deliveries.csv` for stratified matches, containing every expected delivery field above and stable event order.
- `innings_summary.csv` with innings score, wickets, legal balls, end status, targets/revised targets and authoritative scorecard URL/reference.
- `match_crosswalk.csv` with documented evidence linking provider match IDs to official match IDs.
- `player_register.csv` and reviewed `player_crosswalk.csv` with stable namespace and roster/team/date evidence; no name-only join.
- Independent full-match scorecards/source records (or URLs and retrievable artifact hashes) for endpoint and result reconciliation.
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, help="Optional provider bundle directory; defaults to current response path")
    parser.add_argument("--output-dir", type=Path, default=REPORTS,
                        help="Audit output directory (default: outputs/reports); never a data destination")
    args = parser.parse_args()
    if args.bundle:
        gate = write_bundle_validation(args.bundle, args.output_dir)
    else:
        if args.output_dir != REPORTS:
            parser.error("--output-dir is supported only together with --bundle")
        write_current_reports()
    print(f"Wrote Phase 3E audit outputs under {args.output_dir if args.bundle else REPORTS}; gate={gate['status'] if args.bundle else 'current bundle report'}")
