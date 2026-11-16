"""Research-only player and venue crosswalk candidates for the Phase 2F controls.

This module writes isolated research reports. It never edits source data or
Phase 2F reconciliation outputs. Exact player names are verified only when
team and competition context are unique; aliases and fuzzy suggestions remain
unverified candidates.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from difflib import SequenceMatcher
import csv
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
EXTERNAL = ROOT / "data" / "external" / "cricsheet" / "pilot"
JSON_DIR = EXTERNAL / "matches"
REGISTER_DIR = EXTERNAL / "register"
REPORTS = ROOT / "outputs" / "reports"
CONTROL_FILES = {
    13511: "1256720.json",
    20182: "1359476.json",
    34429: "1442989.json",
    40725: "1473469.json",
}
VERIFIED_SCORECARD = {
    40725: "https://www.ipl.com/matches/indian-premier-league-129413/delhi-capitals-vs-rajasthan-royals-87731/scorecard"
}
VENUE_NAME_ALIASES = {
    "punjabcricketassociationisbindrastadiummohalichandigarh":
        "punjabcricketassociationstadiummohalichandigarh",
}


def normalize_name(value: object) -> str:
    """Case, punctuation, and accent normalization only; no fuzzy matching."""
    normalized = unicodedata.normalize("NFKD", str(value or "").casefold())
    plain = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return "".join(ch for ch in plain if ch.isalnum())


def _alias_signature(value: object) -> tuple[str, str, bool] | None:
    """Conservative first-initial + final surname signature for candidate search."""
    raw_words = re.findall(r"[A-Za-z0-9]+", str(value or ""))
    words = [word.casefold() for word in raw_words]
    if len(words) < 2:
        return None
    abbreviated = len(words[0]) == 1 or (len(words[0]) <= 4 and raw_words[0].isupper())
    return words[0][0], words[-1], abbreviated


def resolve_player_candidate(
    local_name: str,
    external_people: list[dict[str, str]],
    *,
    local_duplicate: bool = False,
) -> dict[str, object]:
    """Resolve one local name against roster-scoped external candidates.

    ``external_people`` must already be restricted to the same match team. A
    single exact name with a registry ID is verified. Alias and fuzzy matches
    are always candidates, never automatic identity decisions.
    """
    local_norm = normalize_name(local_name)
    exact = [p for p in external_people if local_norm and normalize_name(p.get("name", "")) == local_norm]
    if exact:
        ids = sorted({str(p.get("registry_id", "")) for p in exact if p.get("registry_id")})
        names = sorted({str(p.get("name", "")) for p in exact})
        if local_duplicate or len(ids) > 1 or len(exact) > 1 and len(names) > 1:
            status = "ambiguous"
            reason = "Exact-name candidate is not unique across the local or Cricsheet roster context."
        elif len(ids) == 1:
            status = "verified"
            reason = "Unique exact normalized name, same match team roster and competition context, with a match-register ID."
        else:
            status = "candidate"
            reason = "Exact roster name is present but no unique Cricsheet register ID is available."
        return {"status": status, "method": "exact_name_team_competition", "candidates": exact,
                "reason": reason, "evidence": "Local competition/team mapping and delivery participant match the Cricsheet match roster."}

    local_alias = _alias_signature(local_name)
    alias = []
    for person in external_people:
        external_alias = _alias_signature(person.get("name", ""))
        if (local_alias and external_alias and local_alias[:2] == external_alias[:2]
                and local_alias[2] != external_alias[2]):
            alias.append(person)
    if alias:
        ids = {str(p.get("registry_id", "")) for p in alias}
        status = "ambiguous" if local_duplicate or len(ids) > 1 or len(alias) > 1 else "candidate"
        reason = ("Initial/surname alias has multiple possible roster identities." if status == "ambiguous"
                  else "Initial/surname alias is a candidate only; no automatic identity acceptance.")
        return {"status": status, "method": "initial_surname_alias_candidate", "candidates": alias,
                "reason": reason, "evidence": "Same match team and competition roster; abbreviated name requires independent confirmation."}

    local_key = normalize_name(local_name)
    fuzzy = [p for p in external_people if local_key and
             SequenceMatcher(None, local_key, normalize_name(p.get("name", ""))).ratio() >= 0.86]
    if fuzzy:
        # Fuzzy suggestions are never verified and remain visible for review.
        status = "ambiguous" if local_duplicate or len({p.get("registry_id", "") for p in fuzzy}) > 1 else "candidate"
        return {"status": status, "method": "spelling_similarity_suggestion", "candidates": fuzzy,
                "reason": "Possible spelling variation from string similarity only; manual independent review required.",
                "evidence": "Same match team and competition roster; similarity is discovery evidence, not identity proof."}

    surname_hits = [p for p in external_people if local_alias and
                    _alias_signature(p.get("name", "")) and
                    local_alias[1] == _alias_signature(p.get("name", ""))[1]]
    if surname_hits:
        status = "ambiguous" if local_duplicate or len({p.get("registry_id", "") for p in surname_hits}) > 1 else "candidate"
        return {"status": status, "method": "surname_context_candidate", "candidates": surname_hits,
                "reason": "Surname and team roster provide a discovery lead only; given-name identity is not confirmed.",
                "evidence": "Same match team and competition roster; surname-only candidate requires independent review."}

    return {"status": "unresolved", "method": "no_contextual_candidate", "candidates": [],
            "reason": "No exact, conservative alias, or spelling-similarity candidate in the same team roster.",
            "evidence": "Local and Cricsheet match/team context inspected; no candidate was identified."}


def resolve_venue_candidate(
    local_venue_id: str,
    external_venue_name: str,
    venue_register: list[dict[str, str]],
    *,
    context_unique: bool,
    authoritative_source_url: str = "",
) -> dict[str, object]:
    """Match the external venue name to its register, retaining local-ID status."""
    external_norm = normalize_name(external_venue_name)
    hits = [r for r in venue_register if external_norm and external_norm in {
        normalize_name(r.get("name", "")), normalize_name(r.get("unique_name", ""))
    }]
    method = "exact_venue_register_name_and_match_context"
    if not hits and external_norm in VENUE_NAME_ALIASES:
        alias_target = VENUE_NAME_ALIASES[external_norm]
        hits = [r for r in venue_register if alias_target in {
            normalize_name(r.get("name", "")), normalize_name(r.get("unique_name", ""))
        }]
        if hits:
            method = "venue_name_alias_candidate"
    identifiers = sorted({str(r.get("identifier", "")) for r in hits if r.get("identifier")})
    if not hits:
        return {"status": "unresolved", "external_venue_id": "", "method": "no_register_name_match",
                "reason": "Cricsheet venue name did not match a unique name or unique_name in its venue register."}
    if len(identifiers) != 1 or not context_unique:
        return {"status": "ambiguous", "external_venue_id": ";".join(identifiers),
                "method": "venue_register_name_or_context_collision",
                "reason": "Venue register or match context produced multiple possible links."}
    status = "verified" if authoritative_source_url else "candidate"
    reason = ("Unique match context and independent authoritative scorecard names this venue; local venue ID is linked through that fixture."
              if status == "verified" else
              "Unique Cricsheet venue-register match and match context; local numeric ID has no documented namespace, so link remains a candidate.")
    if method == "venue_name_alias_candidate":
        status = "candidate"
        reason = "Cricsheet venue name differs from the register label by the observed IS Bindra naming; treat as a candidate pending independent confirmation."
    return {"status": status, "external_venue_id": identifiers[0], "method": method,
            "reason": reason}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_crosswalks() -> dict[str, object]:
    matches = {int(r["match_id"]): r for r in _read_csv(RAW / "matches.csv")}
    competitions = {r["comp_id"]: r for r in _read_csv(RAW / "competitions.csv")}
    team_players = _read_csv(RAW / "competition_team_player_mapping.csv")
    balls = _read_csv(RAW / "ball_by_ball.csv")
    people_register = _read_csv(REGISTER_DIR / "people.csv")
    venue_register = _read_csv(REGISTER_DIR / "venues.csv")
    people_by_id = {r["identifier"]: r for r in people_register}
    global_name_ids: dict[str, set[str]] = defaultdict(set)
    for person in people_register:
        global_name_ids[normalize_name(person.get("name", ""))].add(person.get("identifier", ""))

    player_rows: list[dict[str, object]] = []
    venue_rows: list[dict[str, object]] = []
    all_player_statuses: Counter[str] = Counter()
    venue_statuses: Counter[str] = Counter()

    for match_id, filename in CONTROL_FILES.items():
        local_match = matches[match_id]
        comp = competitions[local_match["comp_id"]]
        payload = json.loads((JSON_DIR / filename).read_text(encoding="utf-8"))
        info = payload.get("info", {})
        registry = info.get("registry", {}).get("people", {}) or {}
        roster = info.get("players", {}) or {}
        external_teams = [str(x) for x in info.get("teams", [])]
        match_date = local_match["match_date"]
        local_teams = [local_match["home_team"], local_match["away_team"]]
        # Local participant ID -> source names and team; include the official
        # comp/team/player mapping name as a second provenance field.
        participants: dict[tuple[str, str], dict[str, object]] = {}
        for ball in balls:
            if int(ball["match_id"]) != match_id:
                continue
            for id_col, name_col, team_col in (
                ("striker_id", "striker_name", "batting_team_id"),
                ("non_striker_id", "non_striker_name", "batting_team_id"),
                ("bowler_id", "bowler_name", "bowling_team_id"),
            ):
                player_id = ball.get(id_col, "")
                team_id = ball.get(team_col, "")
                if not player_id or not team_id:
                    continue
                key = (str(team_id), str(player_id))
                item = participants.setdefault(key, {"names": Counter(), "roles": set()})
                if ball.get(name_col):
                    item["names"][ball[name_col]] += 1
                item["roles"].add(id_col.removesuffix("_id"))

        map_by_key: dict[tuple[str, str, str], set[str]] = defaultdict(set)
        for row in team_players:
            if row["comp_id"] == local_match["comp_id"]:
                map_by_key[(row["comp_id"], row["team_id"], row["player_id"])].add(row["player_name"])

        # Local duplicate-name check is scoped to competition and team.
        local_name_ids: dict[tuple[str, str], set[str]] = defaultdict(set)
        for (team_id, player_id), item in participants.items():
            mapped_names = map_by_key.get((local_match["comp_id"], team_id, player_id), set())
            observed = item["names"]
            name = sorted(mapped_names)[0] if mapped_names else (observed.most_common(1)[0][0] if observed else "")
            local_name_ids[(team_id, normalize_name(name))].add(player_id)

        for (team_id, player_id), item in sorted(participants.items()):
            mapped_names = sorted(map_by_key.get((local_match["comp_id"], team_id, player_id), set()))
            observed_names = item["names"]
            local_name = sorted(mapped_names)[0] if mapped_names else (observed_names.most_common(1)[0][0] if observed_names else "")
            team_rows = [r for r in team_players if r["comp_id"] == local_match["comp_id"] and r["team_id"] == team_id]
            local_team = team_rows[0]["team_name"] if team_rows else ""
            external_team = next((team for team in external_teams if normalize_name(team) == normalize_name(local_team)), "")
            external_roster = roster.get(external_team, []) if external_team else []
            external_people = []
            for display in external_roster:
                identifier = str(registry.get(display, ""))
                reg_person = people_by_id.get(identifier, {})
                external_people.append({"name": str(display), "registry_id": identifier,
                                        "register_name": str(reg_person.get("name", ""))})
            duplicate = len(local_name_ids[(team_id, normalize_name(local_name))]) > 1 if local_name else False
            resolution = resolve_player_candidate(local_name, external_people, local_duplicate=duplicate)
            candidates = resolution["candidates"]
            external_name = " | ".join(sorted({str(x["name"]) for x in candidates}))
            external_ids = sorted({str(x["registry_id"]) for x in candidates if x.get("registry_id")})
            collision_ids = sorted(global_name_ids.get(normalize_name(local_name), set()))
            status = str(resolution["status"])
            all_player_statuses[status] += 1
            player_rows.append({
                "match_id": match_id, "match_date": match_date, "comp_id": local_match["comp_id"],
                "competition": comp["comp_name"], "local_team_id": team_id, "local_team": local_team,
                "external_team": external_team, "local_player_id": player_id,
                "local_competition_mapping_name": " | ".join(mapped_names),
                "local_delivery_names": " | ".join(sorted(observed_names)),
                "roles_observed": ";".join(sorted(item["roles"])),
                "cricsheet_player_name_candidate": external_name,
                "cricsheet_registry_id_candidate": ";".join(external_ids),
                "global_same_name_registry_ids": ";".join(collision_ids),
                "status": status, "match_method": resolution["method"],
                "candidate_count": len(candidates), "evidence": resolution["evidence"],
                "decision_reason": resolution["reason"], "cricsheet_file": filename,
            })

        # Context uniquely identifies each downloaded fixture by date, exact
        # team pair, competition family and event/match number; venue is then
        # read from Cricsheet and matched to its own register.
        external_venue = str(info.get("venue", ""))
        event = info.get("event", {}) if isinstance(info.get("event", {}), dict) else {}
        event_name_norm = normalize_name(event.get("name", ""))
        local_comp_name = str(comp["comp_name"])
        is_ipl = local_comp_name.casefold().startswith("ipl ")
        competition_context = ("indianpremierleague" in event_name_norm or "ipl" in event_name_norm) if is_ipl else all(
            normalize_name(team) in event_name_norm for team in local_teams
        )
        try:
            match_number_context = int(float(local_match["match_number"])) == int(float(event.get("match_number")))
        except (TypeError, ValueError):
            match_number_context = False
        context_unique = (
            match_date in [str(d) for d in info.get("dates", [])]
            and {normalize_name(x) for x in local_teams} == {normalize_name(x) for x in external_teams}
            and str(info.get("match_type", "")).casefold() == "t20"
            and competition_context and match_number_context
        )
        venue_resolution = resolve_venue_candidate(
            local_match["venue_id"], external_venue, venue_register,
            context_unique=context_unique,
            authoritative_source_url=VERIFIED_SCORECARD.get(match_id, ""),
        )
        venue_statuses[str(venue_resolution["status"])] += 1
        external_venue_ids = [str(venue_resolution.get("external_venue_id", ""))]
        venue_name_ids = [r["identifier"] for r in venue_register
                          if normalize_name(external_venue) in {normalize_name(r.get("name", "")), normalize_name(r.get("unique_name", ""))}]
        venue_rows.append({
            "match_id": match_id, "match_date": match_date, "comp_id": local_match["comp_id"],
            "competition": comp["comp_name"], "local_teams": " | ".join(local_teams),
            "cricsheet_teams": " | ".join(external_teams), "local_venue_id": local_match["venue_id"],
            "local_venue_name": "", "local_venue_id_match_count": sum(1 for r in matches.values() if r["venue_id"] == local_match["venue_id"]),
            "cricsheet_venue_name": external_venue, "cricsheet_venue_register_id": ";".join(external_venue_ids),
            "cricsheet_venue_register_exact_name_match_count": len(set(venue_name_ids)),
            "match_context_identity": "exact" if context_unique else "unresolved_or_mismatched",
            "status": venue_resolution["status"], "match_method": venue_resolution["method"],
            "evidence": "Unique date/team/competition match context; Cricsheet venue name checked against Cricsheet venue register.",
            "decision_reason": venue_resolution["reason"],
            "authoritative_source_url": VERIFIED_SCORECARD.get(match_id, ""),
            "cricsheet_file": filename,
        })
    _write_csv(REPORTS / "player_identity_crosswalk.csv", player_rows)
    _write_csv(REPORTS / "venue_identity_crosswalk.csv", venue_rows)
    report = _build_report(player_rows, venue_rows, all_player_statuses, venue_statuses)
    (REPORTS / "identity_crosswalk_report.md").write_text(report, encoding="utf-8")
    return {"control_matches": len(CONTROL_FILES), "player_rows": len(player_rows),
            "player_status_counts": dict(all_player_statuses), "venue_status_counts": dict(venue_statuses),
            "player_report": str(REPORTS / "player_identity_crosswalk.csv"),
            "venue_report": str(REPORTS / "venue_identity_crosswalk.csv"),
            "summary_report": str(REPORTS / "identity_crosswalk_report.md")}


def _build_report(player_rows: list[dict[str, object]], venue_rows: list[dict[str, object]],
                  player_statuses: Counter[str], venue_statuses: Counter[str]) -> str:
    player_matches = {int(r["match_id"]) for r in player_rows}
    player_unique = {int(r["match_id"]) for r in player_rows if r["status"] == "verified"}
    venue_unique = {int(r["match_id"]) for r in venue_rows if r["status"] == "verified"}
    aliases = [r for r in player_rows if r["match_method"] == "initial_surname_alias_candidate"]
    fuzzy = [r for r in player_rows if r["match_method"] == "spelling_similarity_suggestion"]
    collisions = [r for r in player_rows if r["global_same_name_registry_ids"] and ";" in str(r["global_same_name_registry_ids"])]
    duplicates: dict[tuple[int, str, str], set[str]] = defaultdict(set)
    for row in player_rows:
        duplicates[(int(row["match_id"]), str(row["local_team_id"]), normalize_name(row["local_competition_mapping_name"]))].add(str(row["local_player_id"]))
    local_dup_count = sum(len(ids) > 1 for (_, _, name), ids in duplicates.items() if name)
    report = [
        "# Phase 2F.4 — player and venue identity crosswalk research", "",
        "## Scope and guardrails", "",
        "Research uses the four downloaded controls (13511, 20182, 34429, 40725), canonical local competition/player/match/delivery records, Cricsheet match rosters and per-match person registry, and Cricsheet People/Venue registers. The crosswalk CSVs are isolated research outputs. No raw file, existing reconciliation decision, comparator acceptance, or Phase 2F decision was changed.", "",
        "Player `verified` means a unique exact normalized name appears in the same local competition/team mapping and the Cricsheet roster for the exact match, with one match-register identifier. It verifies a match-context identity candidate; it does **not** establish that the local numeric player ID and Cricsheet ID share a namespace. Initial/surname aliases and spelling-similarity suggestions are always `candidate`; no fuzzy match is automatically accepted. Duplicate or conflicting identity candidates are `ambiguous`.", "",
        "For venues, the official local source contains an opaque numeric `venue_id` but no venue name. Cricsheet names are matched to its venue register. A local-ID link is `verified` only when an independent authoritative scorecard supports the exact fixture (currently match 40725); a unique Cricsheet name plus date/team context alone remains a `candidate`.", "",
        "## Coverage", "",
        f"- **Players:** {len(player_rows)} match-scoped local player IDs across {len(player_matches)} controls. Status counts: {dict(player_statuses)}; {player_statuses.get('verified', 0)}/{len(player_rows)} ({player_statuses.get('verified', 0) / max(1, len(player_rows)):.1%}) are verified exact-name/team/competition context mappings. At least one verified mapping occurs in {len(player_unique)}/4 controls. These are research coverage counts, not permission to use IDs in the production join.",
        f"- **Venues:** {len(venue_rows)} local venue-ID/match rows across 4 controls. Status counts: {dict(venue_statuses)}. Verified links occur in {len(venue_unique)}/4 controls; remaining links are candidates or unresolved.", "",
        "## Player findings", "",
        f"The conservative initials/surname rule generated {len(aliases)} candidates; {sum(r['match_method'] == 'surname_context_candidate' for r in player_rows)} additional surname-only candidates and {len(fuzzy)} spelling-similarity suggestions were generated. All remain unverified by design. There are {len(collisions)} rows whose normalized local name has multiple identifiers in the global Cricsheet People register, and {local_dup_count} duplicate local-name groups within match/team scopes. The row-level files retain candidate names, IDs, context, method, evidence, and reason.", "",
        "Two ambiguous rows occur in match 34429: local Kusal Mendis (ID 3672) and Kamindu Mendis (ID 4904) both have three same-team Cricsheet `Mendis` surname candidates. Neither is forced to a specific player. The Cricsheet People register also has duplicate display-name IDs for 20182 Mandeep Singh; the match JSON registry maps its roster entry to one match-specific ID. The crosswalk records that global name collision while keeping the local and Cricsheet ID namespaces separate.", "",
        "Initial-name aliases include full local names paired with Cricsheet initials forms, for example `Nitish Rana` / `N Rana` and `Yashasvi Jaiswal` / `YBK Jaiswal`; these remain candidates. No player spelling-similarity suggestions met the configured review threshold in these four control cohorts, so no spelling variation is asserted from the data. The venue name `Punjab Cricket Association IS Bindra Stadium, Mohali, Chandigarh` differs from the venue-register label `Punjab Cricket Association Stadium, Mohali, Chandigarh`; the venue crosswalk keeps this as a candidate alias.", "",
        "## Venue findings", "",
        "| Match | Local venue ID | Cricsheet venue | Venue register ID | Status | Evidence |",
        "|---:|---:|---|---|---|---|"]
    for row in venue_rows:
        source = "Official IPL scorecard" if row["authoritative_source_url"] else "Cricsheet venue register + exact fixture context"
        report.append(f"| {row['match_id']} | {row['local_venue_id']} | {row['cricsheet_venue_name']} | {row['cricsheet_venue_register_id']} | {row['status']} | {source} |")
    report.extend([
        "", "The four local venue IDs occur in multiple local match records, but the canonical local files still provide no venue labels or venue-ID namespace. The Cricsheet venue register’s external keys did not equal local IDs 54, 79, 105, or 7. Therefore, the three non-scorecard links remain candidates despite exact match context. Match 40725 is linked to Arun Jaitley Stadium by the official IPL scorecard and its unique date/team fixture context.", "",
        "## Duplicate names, aliases, spelling and conflicts", "",
        "- Exact case/punctuation/accent normalization is used for exact names; it does not merge different spellings automatically.",
        "- Initial/surname aliases, surname-only leads, and any spelling-similarity suggestions are retained as candidates only.",
        "- Multiple external IDs for an exact name, duplicate local names in the same team/competition, or multiple external roster candidates produce `ambiguous` rows.",
        "- `global_same_name_registry_ids` exposes name collisions in Cricsheet's global People register even when the match JSON contains one match-specific registry assignment.",
        "- No candidate is forced to verified based on team, season, or fuzzy similarity alone.", "",
        "## Files", "",
        "- `player_identity_crosswalk.csv`: one row per local participant ID per control match, including candidate identity, team/competition context, evidence and decision reason.",
        "- `venue_identity_crosswalk.csv`: one row per control fixture linking local venue ID to the Cricsheet venue register and recording evidence/status.",
        "## Provenance", "",
        "Cricsheet match JSON archives: `https://cricsheet.org/downloads/ipl_json.zip` and `https://cricsheet.org/downloads/t20s_json.zip`. Cricsheet registers: [`people.csv`](https://cricsheet.org/register/people.csv) and [`venues.csv`](https://cricsheet.org/register/venues.csv), ODC-BY 1.0. The match 40725 venue corroboration is the [official IPL scorecard](https://www.ipl.com/matches/indian-premier-league-129413/delhi-capitals-vs-rajasthan-royals-87731/scorecard). Local identity context comes from `competition_team_player_mapping.csv`, `competitions.csv`, `matches.csv`, and `ball_by_ball.csv`.", "",
        "This is identity research only. It does not revise the Phase 2F player crosswalk, accept a match, or change player eligibility or rankings.", ""
    ])
    return "\n".join(report)


if __name__ == "__main__":
    print(json.dumps(build_crosswalks(), indent=2))
