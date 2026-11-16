"""Deterministic Cricsheet reconciliation pilot; source rows remain immutable.

Downloads use HTTP byte ranges against Cricsheet ZIPs and save only selected JSON
members. The containing ZIP archives are never written to disk.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import csv
import hashlib
import json
import math
import re
import struct
import zipfile
import urllib.request
from urllib.error import HTTPError, URLError
import zlib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
EXTERNAL = ROOT / "data" / "external" / "cricsheet" / "pilot"
MATCH_DIR = EXTERNAL / "matches"
REPORTS = ROOT / "outputs" / "reports"

# Cricsheet's wickets array can contain a retirement event as well as a
# dismissal. Keep event markers, team wickets lost, and bowler credit distinct.
_BOWLER_CREDIT_KINDS = {
    "bowled", "caught", "caughtandbowled", "hitwicket", "lbw", "stumped",
}


def _kind_key(kind: object) -> str:
    return "".join(ch for ch in str(kind or "").casefold() if ch.isalnum())


def _team_wickets_lost(wickets: list[dict[str, object]] | None) -> int:
    """Count dismissals as team wickets; retired hurt is only an event marker."""
    return sum(_kind_key(w.get("kind")) != "retiredhurt" for w in (wickets or []))


def _bowler_credited_wickets(wickets: list[dict[str, object]] | None) -> int:
    """Count only recognized bowler-credit dismissal kinds, separately."""
    return sum(_kind_key(w.get("kind")) in _BOWLER_CREDIT_KINDS for w in (wickets or []))
CRICSHEET_DOWNLOADS = "https://cricsheet.org/downloads/"
CRICSHEET_LICENSE = "Open Data Commons Attribution License 1.0 (ODC-BY 1.0)"

# All 16 local matches with no delivery rows, plus four deterministic controls.
# Candidate matches are non-Afghanistan IPL/T20I records and are included even
# though the official result is abandoned; source availability is the question.
PILOT_IDS = [
    31281, 31284, 31288, 40761,  # missing IPL delivery records
    32610, 32612, 32622, 38797, 36564, 36210, 41502, 41503, 42030, 46008, 48513, 50189,  # missing T20I rows
    20182, 40725, 13511, 34429,  # controls: DLS, IPL super over, regular T20I, T20I super over
]
CONTROL_IDS = {20182, 40725, 13511, 34429}
ARCHIVES = {
    "IPL": "https://cricsheet.org/downloads/ipl_json.zip",
    "T20I": "https://cricsheet.org/downloads/t20s_json.zip",
}
# Cricsheet JSON ZIP members are named with numeric Cricsheet/Cricinfo IDs.
# The companion Ashwin CSV ZIP carries one compact *_info.csv per match. Those
# metadata members are read in memory only to resolve numeric JSON IDs; none of
# the CSV archive or its delivery data is extracted to disk or merged.
MATCH_INDEX_ARCHIVES = {
    "IPL": "https://cricsheet.org/downloads/ipl_csv2.zip",
    "T20I": "https://cricsheet.org/downloads/t20s_csv2.zip",
}
TEAM_ALIASES = {
    "Chennai Super Kings": ["chennai super kings", "csk"],
    "Kolkata Knight Riders": ["kolkata knight riders", "kkr"],
    "Gujarat Titans": ["gujarat titans", "gt"],
    "Sunrisers Hyderabad": ["sunrisers hyderabad", "srh"],
    "Rajasthan Royals": ["rajasthan royals", "rr"],
    "Delhi Capitals": ["delhi capitals", "dc"],
    "Punjab Kings": ["punjab kings", "pbks", "kings xi punjab", "kxip"],
    "Royal Challengers Bengaluru": ["royal challengers bengaluru", "royal challengers bangalore", "rcb"],
    "Mumbai Indians": ["mumbai indians", "mi"],
    "Lucknow Super Giants": ["lucknow super giants", "lsg"],
    "West Indies": ["west indies", "windies", "wi"],
    "England": ["england", "eng"], "Pakistan": ["pakistan", "pak"],
    "Ireland": ["ireland", "ire"], "Scotland": ["scotland", "sco"],
    "South Africa": ["south africa", "sa"], "Australia": ["australia", "aus"],
    "India": ["india", "ind"], "Sri Lanka": ["sri lanka", "sl"],
    "New Zealand": ["new zealand", "nz"], "Bangladesh": ["bangladesh", "ban"],
    "Zimbabwe": ["zimbabwe", "zim"], "Netherlands": ["netherlands", "ned"],
}
BOWLER_CREDITED = {"bowled", "caught", "caught and bowled", "lbw", "stumped", "hit wicket", "hit the ball twice"}


def _norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _team_key(value: object) -> str:
    normalized = _norm(value)
    for canonical, aliases in TEAM_ALIASES.items():
        if normalized in {_norm(canonical), *(_norm(x) for x in aliases)}:
            return _norm(canonical)
    return normalized


def _read_range(url: str, start: int, end: int) -> bytes:
    request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}", "User-Agent": "RR-Pressure-X-reconciliation/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        if response.status != 206:
            raise RuntimeError(f"Range request refused for {url}: HTTP {response.status}; refusing whole-archive download")
        content_range = response.headers.get("Content-Range", "")
        if not content_range.startswith(f"bytes {start}-"):
            raise RuntimeError(f"Unexpected Content-Range {content_range!r} for {url}")
        data = response.read()
    expected = end - start + 1
    if len(data) != expected:
        raise RuntimeError(f"Range size mismatch for {url}: expected {expected}, got {len(data)}")
    return data


def zip_directory(url: str) -> list[dict[str, object]]:
    """Read only ZIP metadata via HTTP ranges; never persist the archive."""
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "RR-Pressure-X-reconciliation/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        total = int(response.headers["Content-Length"])
        if "bytes" not in response.headers.get("Accept-Ranges", "").casefold():
            raise RuntimeError(f"Server does not advertise byte ranges for {url}; refusing archive download")
    tail_length = min(total, 65557)
    tail_start = total - tail_length
    tail = _read_range(url, tail_start, total - 1)
    eocd_at = tail.rfind(b"PK\x05\x06")
    if eocd_at < 0 or len(tail) - eocd_at < 22:
        raise RuntimeError(f"ZIP end-of-central-directory not found for {url}")
    record = struct.unpack_from("<4s4H2LH", tail, eocd_at)
    _, disk_no, cd_disk, entries_disk, entries_total, cd_size, cd_offset, comment_len = record
    if disk_no or cd_disk or entries_disk != entries_total or entries_total == 0xFFFF or cd_offset == 0xFFFFFFFF:
        raise RuntimeError(f"Unsupported multi-disk/ZIP64 archive: {url}")
    if eocd_at + 22 + comment_len > len(tail):
        raise RuntimeError(f"Truncated ZIP comment for {url}")
    cd = _read_range(url, cd_offset, cd_offset + cd_size - 1)
    entries = []
    pos = 0
    header = struct.Struct("<4s6H3I5H2I")
    while pos < len(cd):
        if len(cd) - pos < header.size:
            raise RuntimeError(f"Truncated central directory for {url}")
        values = header.unpack_from(cd, pos)
        if values[0] != b"PK\x01\x02":
            raise RuntimeError(f"Invalid central directory signature for {url}")
        flags, method = values[3], values[4]
        crc32, compressed_size, file_size = values[7], values[8], values[9]
        name_len, extra_len, comment_len, disk_start = values[10], values[11], values[12], values[13]
        local_offset = values[16]
        start = pos + header.size
        filename_bytes = cd[start:start + name_len]
        encoding = "utf-8" if flags & 0x800 else "cp437"
        filename = filename_bytes.decode(encoding)
        entries.append({"filename": filename, "flags": flags, "method": method, "crc32": crc32,
            "compressed_size": compressed_size, "file_size": file_size, "local_offset": local_offset,
            "directory": filename.endswith("/")})
        pos = start + name_len + extra_len + comment_len
    return entries


def read_zip_member(url: str, entry: dict[str, object]) -> bytes:
    """Range-fetch and decompress one central-directory-selected ZIP member."""
    if entry["directory"]:
        raise ValueError("Cannot read a ZIP directory member")
    if int(entry["flags"]) & 0x1:
        raise RuntimeError("Encrypted ZIP member is unsupported")
    offset = int(entry["local_offset"])
    fixed = _read_range(url, offset, offset + 29)
    values = struct.unpack("<4s5H3I2H", fixed)
    if values[0] != b"PK\x03\x04":
        raise RuntimeError("Invalid local file header")
    name_len, extra_len = values[9], values[10]
    data_offset = offset + 30 + name_len + extra_len
    compressed = _read_range(url, data_offset, data_offset + int(entry["compressed_size"]) - 1)
    method = int(entry["method"])
    if method == 0:
        raw = compressed
    elif method == 8:
        raw = zlib.decompress(compressed, -15)
    else:
        raise RuntimeError(f"Unsupported ZIP compression method {method}")
    if len(raw) != int(entry["file_size"]) or (zlib.crc32(raw) & 0xFFFFFFFF) != int(entry["crc32"]):
        raise RuntimeError(f"Integrity failure for ZIP member {entry['filename']}")
    return raw


def _parse_info_member(content: bytes, fallback_match_id: str = "") -> list[dict[str, object]]:
    """Extract match key metadata from one Cricsheet Ashwin *_info.csv member."""
    try:
        rows = list(csv.reader(BytesIO(content).read().decode("utf-8-sig").splitlines()))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError(f"Invalid Cricsheet info CSV: {exc}") from exc
    values: dict[str, list[str]] = {}
    for row in rows:
        if len(row) >= 3 and row[0] == "info":
            values.setdefault(row[1], []).append(row[2])
    match_ids = values.get("match_id", []) or [fallback_match_id]
    dates = values.get("date", [])
    teams = values.get("team", [])
    gender = (values.get("gender") or [""])[0].casefold()
    if not match_ids or not dates or len(set(teams)) < 2:
        return []
    pair = tuple(sorted((_team_key(teams[0]), _team_key(teams[1]))))
    records = []
    for match_id in set(match_ids):
        for date in set(dates):
            parsed_date = pd.to_datetime(date, errors="coerce")
            if pd.isna(parsed_date):
                continue
            records.append({"match_id": str(match_id), "start_date": parsed_date.strftime("%Y-%m-%d"),
                "team_pair_key": pair, "gender": gender})
    return records


def _load_match_index_archive(url: str) -> tuple[pd.DataFrame, str, int]:
    """Read only per-match info CSV members from a companion ZIP, in memory."""
    request = urllib.request.Request(url, headers={"User-Agent": "RR-Pressure-X-reconciliation/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        if response.status != 200:
            raise RuntimeError(f"Match-index request failed for {url}: HTTP {response.status}")
        archive_bytes = response.read()
    if not archive_bytes.startswith(b"PK\x03\x04"):
        raise ValueError(f"Expected ZIP response from {url}; received non-ZIP content")
    records = []
    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        info_names = [name for name in archive.namelist() if name.casefold().endswith("_info.csv")]
        for name in info_names:
            records.extend(_parse_info_member(archive.read(name), Path(name).name.removesuffix("_info.csv")))
    if not records:
        raise ValueError(f"No match metadata members found in {url}")
    frame = pd.DataFrame(records).drop_duplicates(["match_id", "start_date", "team_pair_key"])
    return frame.reset_index(drop=True), hashlib.sha256(archive_bytes).hexdigest(), len(info_names)


def _match_index_candidates(index: pd.DataFrame, row: pd.Series) -> list[str]:
    """Find numeric Cricsheet IDs by date, both teams, and competition archive.

    This is candidate discovery only. The selected JSON's event and venue are
    still checked separately before the reconciliation acceptance gate.
    """
    target_date = pd.to_datetime(row["match_date"], errors="coerce")
    if pd.isna(target_date):
        return []
    target_pair = tuple(sorted((_team_key(row["home_team"]), _team_key(row["away_team"]))))
    same_date = index["start_date"].eq(target_date.strftime("%Y-%m-%d"))
    same_teams = index["team_pair_key"].map(lambda pair: pair == target_pair)
    selected = index[same_date & same_teams]
    if str(row.get("match_format", "")).casefold() == "t20i" and "gender" in selected.columns:
        selected = selected[selected.gender.astype(str).str.casefold().eq("male")]
    return sorted(selected["match_id"].astype(str).unique().tolist())


def _json_payload(content: bytes, source_name: str = "Cricsheet member") -> dict[str, object]:
    """Decode and validate the top-level shape before saving a selected JSON."""
    try:
        payload = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid JSON response in {source_name}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("info"), dict) or not isinstance(payload.get("innings"), list):
        raise ValueError(f"Unexpected Cricsheet JSON structure in {source_name}")
    return payload


def _numeric_json_entries(entries: list[dict[str, object]], match_ids: list[str]) -> list[dict[str, object]]:
    wanted = {str(match_id) for match_id in match_ids}
    return [entry for entry in entries if str(entry["filename"]).casefold().endswith(".json")
            and Path(str(entry["filename"])).stem in wanted]


def _metadata_identity(row: pd.Series, payload: dict[str, object]) -> dict[str, object]:
    info = payload.get("info", {})
    dates = [str(x) for x in info.get("dates", [])]
    teams = [str(x) for x in info.get("teams", [])]
    expected_teams = {_team_key(row["home_team"]), _team_key(row["away_team"])}
    observed_teams = {_team_key(x) for x in teams}
    kind = "IPL" if str(row["comp_name"]).casefold().startswith("ipl ") else "T20I"
    event = info.get("event") or {}
    event_name = str(event.get("name", "")) if isinstance(event, dict) else str(event)
    local_event = str(row["comp_name"])
    event_norm = _norm(event_name)
    local_event_norm = _norm(local_event.replace(str(row["season"]), ""))
    bilateral_event_label = all(_norm(team) in event_norm for team in (row["home_team"], row["away_team"]))
    if kind == "IPL":
        event_ok = "indianpremierleague" in event_norm or "ipl" in event_norm
        event_basis = "ipl_competition_label" if event_ok else "unresolved"
    else:
        event_ok = local_event_norm in event_norm or event_norm in local_event_norm or bilateral_event_label
        event_basis = ("local_event_label" if local_event_norm in event_norm or event_norm in local_event_norm
            else "both_local_teams_in_external_bilateral_event" if bilateral_event_label else "unresolved")
    outcome = info.get("outcome") or {}
    winner = str(outcome.get("winner", "")) if isinstance(outcome, dict) else ""
    match_number = event.get("match_number") if isinstance(event, dict) else None
    venue = str(info.get("venue", ""))
    return {
        "date_match": str(row["match_date"]) in dates,
        "teams_match": expected_teams == observed_teams,
        "format_match": str(info.get("match_type", "")).casefold() == "t20",
        "competition_family_match": (kind == "IPL" and ("ipl" in _norm(event_name) or "indianpremierleague" in _norm(event_name))) or (kind == "T20I" and event_ok),
        "competition_match_basis": event_basis,
        "event_name_external": event_name, "external_match_number": match_number,
        "external_venue": venue, "local_venue_id": row.get("venue_id"),
        "local_venue_country": row.get("venue_country"), "external_winner": winner,
        "external_teams": " | ".join(teams), "external_dates": " | ".join(dates),
        "venue_comparison_status": "unresolved: local venue is an opaque ID without documented namespace/name",
    }


def _registry_people(payload: dict[str, object]) -> dict[str, str]:
    raw = (payload.get("info", {}).get("registry") or {}).get("people", {})
    return {str(name): str(identifier) for name, identifier in raw.items()} if isinstance(raw, dict) else {}


def _flatten_deliveries(payload: dict[str, object]) -> list[dict[str, object]]:
    events = []
    for innings_index, innings in enumerate(payload.get("innings", []), start=1):
        for over in innings.get("overs", []):
            over_number = int(over.get("over", 0)) + 1
            for position, delivery in enumerate(over.get("deliveries", []), start=1):
                runs = delivery.get("runs", {})
                extras = delivery.get("extras", {}) or {}
                wickets = delivery.get("wickets", []) or []
                actual = str(delivery.get("actual_delivery", ""))
                events.append({
                    "innings": innings_index, "over": over_number, "delivery_position": position,
                    "actual_delivery": actual, "batter_name_external": str(delivery.get("batter", delivery.get("batsman", ""))),
                    "non_striker_name_external": str(delivery.get("non_striker", "")),
                    "bowler_name_external": str(delivery.get("bowler", "")),
                    "batter_runs_external": int(runs.get("batter", runs.get("batsman", 0))),
                    "extras_total_external": int(runs.get("extras", 0)), "total_runs_external": int(runs.get("total", 0)),
                    "extras_json": json.dumps(extras, sort_keys=True, ensure_ascii=False),
                    "extras_keys": ";".join(sorted(str(k) for k, v in extras.items() if int(v or 0) != 0)),
                    "wickets_json": json.dumps(wickets, sort_keys=True, ensure_ascii=False),
                    "wicket_count_external": len(wickets),
                    "team_wicket_count_external": _team_wickets_lost(wickets),
                    "bowler_credited_wicket_count_external": _bowler_credited_wickets(wickets),
                    "dismissal_kinds_external": ";".join(str(w.get("kind", "")) for w in wickets),
                    "dismissed_names_external": ";".join(str(w.get("player_out", "")) for w in wickets),
                    "legal_delivery_external_candidate": not bool(int(extras.get("wides", 0) or 0) or int(extras.get("noballs", 0) or 0)),
                    "innings_super_over_external": bool(innings.get("super_over", False)),
                })
    return events


def _flatten_local(local: pd.DataFrame) -> pd.DataFrame:
    if not local.empty and local.duplicated(["match_id", "innings", "innings_ball_num"]).any():
        raise ValueError("Duplicate local delivery coordinates: repeated innings_ball_num")
    rows = []
    for (match_id, innings), group in local.groupby(["match_id", "innings"], sort=True):
        group = group.sort_values("innings_ball_num", kind="stable").copy()
        group["delivery_position"] = group.groupby("overid", sort=False).cumcount() + 1
        for row in group.itertuples(index=False):
            rows.append({
                "match_id": int(match_id), "innings": int(innings), "over": int(row.overid),
                "delivery_position": int(row.delivery_position), "sequence": int(row.innings_ball_num),
                "local_over_ball_num": int(row.over_ball_num), "batter_id_local": int(row.striker_id),
                "batter_name_local": str(row.striker_name), "non_striker_id_local": int(row.non_striker_id),
                "non_striker_name_local": str(row.non_striker_name), "bowler_id_local": int(row.bowler_id),
                "bowler_name_local": str(row.bowler_name), "batter_runs_local_candidate": int(row.runs),
                "extras_type_local": "" if pd.isna(row.extras_type) else str(row.extras_type),
                "extras1_code_local": int(row.extras1_runs), "extras2_local_unresolved": int(row.extras_2_runs),
                "total_runs_local": pd.NA, "total_runs_local_status": "unavailable: source total/extras unresolved",
                "is_wicket_local": bool(row.is_wicket), "dismissal_type_local": "" if pd.isna(row.dismissal_type) else str(row.dismissal_type),
                "dismissed_player_id_local": None if pd.isna(row.dismissed_player_id) else int(row.dismissed_player_id),
                "legal_delivery_local": None if pd.isna(row.legal_delivery) else bool(row.legal_delivery),
                "legal_delivery_status_local": str(row.legal_delivery_status),
            })
    return pd.DataFrame(rows)


def _extra_type_status(local_label: str, external_keys: str) -> tuple[str, str]:
    keys = set(filter(None, external_keys.split(";")))
    if not local_label:
        return ("exact" if not keys else "mismatch", "")
    mapping = {"wide": {"wides"}, "overstep": {"noballs"}, "byes": {"byes"},
        "legbyes": {"legbyes"}, "penalty": {"penalty"}}
    label = local_label.casefold()
    if label == "other":
        return "structural_difference", "official feed category 'other' has no resolved Cricsheet subtype"
    expected = mapping.get(label)
    if expected is None:
        return "unresolved", "no validated type mapping"
    if label == "overstep":
        status = "inferred_mapping_match" if keys == expected else ("inferred_mapping_mismatch" if keys else "unresolved")
        return status, "Overstep-to-no-ball remains an inference, not a provider-confirmed mapping"
    if keys == expected:
        return "type_match_amount_unavailable", "official source has category but no resolved per-type amount"
    return ("mismatch", "") if keys else ("mismatch", "external typed extras absent")


def compare_deliveries(match_id: int, local: pd.DataFrame, external: list[dict[str, object]], crosswalk: dict[tuple[int, int], str]) -> pd.DataFrame:
    local_flat = _flatten_local(local[local.match_id.eq(match_id)])
    ext_frame = pd.DataFrame(external)
    if local_flat.empty and ext_frame.empty:
        return pd.DataFrame()
    if not local_flat.empty and local_flat.duplicated(["innings", "over", "delivery_position"]).any():
        raise ValueError(f"Duplicate local delivery coordinates in match {match_id}")
    if not ext_frame.empty and ext_frame.duplicated(["innings", "over", "delivery_position"]).any():
        raise ValueError(f"Duplicate external delivery coordinates in match {match_id}")
    merged = local_flat.merge(ext_frame, on=["innings", "over", "delivery_position"], how="outer", indicator=True, validate="one_to_one")
    if "match_id" in merged.columns:
        merged["match_id"] = match_id
    else:
        merged.insert(0, "match_id", match_id)
    merged["row_alignment_status"] = merged["_merge"].map({"both": "aligned", "left_only": "local_only", "right_only": "external_only"})
    merged["batter_name_content_match"] = merged.apply(lambda r: _norm(r.get("batter_name_local")) == _norm(r.get("batter_name_external")) if r["_merge"] == "both" else pd.NA, axis=1)
    merged["bowler_name_content_match"] = merged.apply(lambda r: _norm(r.get("bowler_name_local")) == _norm(r.get("bowler_name_external")) if r["_merge"] == "both" else pd.NA, axis=1)
    merged["batter_id_mapping_status"] = merged.apply(lambda r: crosswalk.get((match_id, int(r["batter_id_local"])), "unresolved") if r["_merge"] == "both" and pd.notna(r.get("batter_id_local")) else "unresolved", axis=1)
    merged["bowler_id_mapping_status"] = merged.apply(lambda r: crosswalk.get((match_id, int(r["bowler_id_local"])), "unresolved") if r["_merge"] == "both" and pd.notna(r.get("bowler_id_local")) else "unresolved", axis=1)
    merged["batter_runs_status"] = merged.apply(lambda r: "exact" if r["_merge"] == "both" and int(r["batter_runs_local_candidate"]) == int(r["batter_runs_external"]) else "mismatch" if r["_merge"] == "both" else "unresolved", axis=1)
    merged["total_runs_status"] = merged.apply(lambda r: "exact_on_no_extras_only" if r["_merge"] == "both" and not str(r["extras_type_local"]) and int(r["total_runs_external"]) == int(r["batter_runs_local_candidate"]) else "structural_difference: official per-delivery total/extras amount unavailable" if r["_merge"] == "both" else "unresolved", axis=1)
    extras = merged.apply(lambda r: _extra_type_status(str(r.get("extras_type_local", "")), str(r.get("extras_keys", ""))) if r["_merge"] == "both" else ("unresolved", "delivery unmatched"), axis=1)
    merged["extras_type_status"] = [item[0] for item in extras]
    merged["extras_type_note"] = [item[1] for item in extras]
    merged["extras_amount_status"] = merged.apply(lambda r: "structural_difference: no official per-type amount" if r["_merge"] == "both" and (str(r.get("extras_type_local", "")) or str(r.get("extras_keys", ""))) else "exact_zero_extras" if r["_merge"] == "both" else "unresolved", axis=1)
    merged["legal_delivery_status"] = merged.apply(lambda r: "exact" if r["_merge"] == "both" and pd.notna(r.get("legal_delivery_local")) and bool(r["legal_delivery_local"]) == bool(r["legal_delivery_external_candidate"]) else "mismatch" if r["_merge"] == "both" and pd.notna(r.get("legal_delivery_local")) else "structural_difference: official legal status unknown" if r["_merge"] == "both" else "unresolved", axis=1)
    merged["wicket_count_status"] = merged.apply(lambda r: "exact" if r["_merge"] == "both" and bool(r["is_wicket_local"]) == (int(r.get("team_wicket_count_external", _team_wicket_count_from_kinds(r.get("dismissal_kinds_external", "")))) > 0) else "mismatch" if r["_merge"] == "both" else "unresolved", axis=1)
    merged["dismissal_kind_status"] = merged.apply(lambda r: "unresolved: no local dismissal" if r["_merge"] != "both" else _dismissal_status(r.get("dismissal_type_local"), r.get("dismissal_kinds_external")), axis=1)
    statuses = ["batter_runs_status", "total_runs_status", "extras_type_status", "legal_delivery_status", "wicket_count_status", "dismissal_kind_status"]
    merged["delivery_reconciliation_status"] = merged.apply(lambda r: "mismatch" if r["_merge"] != "both" or any("mismatch" in str(r[c]) for c in statuses) else "partial_match" if any(str(r[c]).startswith(("structural_difference", "inferred_mapping", "type_match_amount")) or str(r[c]).startswith("unresolved") for c in statuses) or not bool(r["batter_id_mapping_status"] == "accepted_exact_namespace") else "exact_match", axis=1)
    return merged.drop(columns=["_merge"])


def _dismissal_status(local_kind: object, external_kinds: object) -> str:
    local = _norm(local_kind)
    external = {_norm(x) for x in str(external_kinds or "").split(";") if x}
    aliases = {"stump": "stumped", "runout": "runout", "obstractingthefield": "obstructingthefield"}
    local = aliases.get(local, local)
    if not local and not external:
        return "exact_no_wicket"
    if not local and external == {"retiredhurt"}:
        return "non_wicket_retirement: retired hurt"
    if local and local in external:
        return "kind_match_player_id_mapping_required"
    return "mismatch" if local or external else "unresolved"


def _team_wicket_count_from_kinds(kinds: object) -> int:
    """Compatibility for direct comparator fixtures lacking flattened counts."""
    return sum(_kind_key(kind) != "retiredhurt" for kind in str(kinds or "").split(";") if kind)


def accept_match(checks: dict[str, object]) -> tuple[str, str]:
    """Apply Phase 2E's zero-unexplained-difference acceptance gate."""
    if checks.get("external_file_status") in {"not_found_in_archive", "ambiguous_archive_members", "download_failed",
            "unresolved_no_match_index_entry", "ambiguous_match_index_candidates", "json_member_missing_from_archive",
            "ambiguous_json_archive_members"}:
        return "unresolved", str(checks.get("external_file_status"))
    if checks.get("match_identity_status") == "mismatch" or checks.get("genuine_mismatch_count", 0):
        return "rejected", "identity or delivery-level disagreement; zero unexplained differences required"
    required = ["player_identity_status", "venue_identity_status", "delivery_sequence_status", "batter_runs_status",
        "extras_amounts_status", "total_runs_status", "legal_balls_status", "wickets_status", "innings_totals_status",
        "target_status", "bowling_figures_status", "result_status"]
    unresolved = [key for key in required if checks.get(key) != "exact"]
    if unresolved:
        return "unresolved", "acceptance blocked by: " + "; ".join(unresolved)
    return "accepted", "all Phase 2E checks exact with zero unexplained differences"


def _load_local() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    matches = pd.read_csv(RAW / "matches.csv", low_memory=False)
    competitions = pd.read_csv(RAW / "competitions.csv", low_memory=False)
    balls = pd.read_csv(RAW / "ball_by_ball.csv", low_memory=False)
    states = pd.read_csv(PROCESSED / "match_state_deliveries.csv.gz", low_memory=False)
    return matches, competitions, balls, states


def _write_run_date() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def download_selected() -> dict[str, object]:
    """Resolve Cricsheet numeric IDs, then retrieve only selected JSON members."""
    matches, competitions, _, _ = _load_local()
    pilot = matches[matches.match_id.isin(PILOT_IDS)].merge(competitions, on="comp_id", validate="many_to_one")
    if len(pilot) != len(PILOT_IDS):
        raise ValueError("Pilot IDs are not unique or are missing from official match tables")
    pilot["pilot_role"] = pilot["match_id"].map(lambda mid: "control" if mid in CONTROL_IDS else "missing_delivery_candidate")
    retrieval = _write_run_date()
    MATCH_DIR.mkdir(parents=True, exist_ok=True)
    index_cache = {fmt: zip_directory(url) for fmt, url in ARCHIVES.items()}
    match_index_cache = {}
    match_index_hash_cache = {}
    match_index_members = {}
    for fmt, url in MATCH_INDEX_ARCHIVES.items():
        frame, archive_sha, info_member_count = _load_match_index_archive(url)
        match_index_cache[fmt] = frame
        match_index_hash_cache[fmt] = archive_sha
        match_index_members[fmt] = f"{info_member_count} *_info.csv members (metadata only)"
    manifests, payloads = [], {}
    for _, row in pilot.iterrows():
        fmt = "IPL" if str(row.comp_name).casefold().startswith("ipl ") else "T20I"
        url = ARCHIVES[fmt]
        lookup_url = MATCH_INDEX_ARCHIVES[fmt]
        ids = _match_index_candidates(match_index_cache[fmt], row)
        lookup_provenance = {"match_index_url": lookup_url,
            "match_index_member": match_index_members[fmt],
            "match_index_member_sha256": match_index_hash_cache[fmt]}
        if len(ids) == 0:
            manifests.append({"match_id": int(row.match_id), "format": fmt, "role": row.pilot_role,
                "external_file_status": "unresolved_no_match_index_entry", "archive_url": url, "archive_member": "",
                "retrieved_utc": retrieval, "license": CRICSHEET_LICENSE, "sha256": "", **lookup_provenance})
            continue
        if len(ids) != 1:
            manifests.append({"match_id": int(row.match_id), "format": fmt, "role": row.pilot_role,
                "external_file_status": "ambiguous_match_index_candidates", "archive_url": url,
                "archive_member": "", "candidate_cricsheet_ids": " | ".join(ids),
                "retrieved_utc": retrieval, "license": CRICSHEET_LICENSE, "sha256": "", **lookup_provenance})
            continue
        candidates = _numeric_json_entries(index_cache[fmt], ids)
        if len(candidates) != 1:
            manifests.append({"match_id": int(row.match_id), "format": fmt, "role": row.pilot_role,
                "external_file_status": "json_member_missing_from_archive" if not candidates else "ambiguous_json_archive_members", "archive_url": url,
                "archive_member": "", "candidate_cricsheet_ids": ids[0],
                "retrieved_utc": retrieval, "license": CRICSHEET_LICENSE, "sha256": "", **lookup_provenance})
            continue
        entry = candidates[0]
        try:
            content = read_zip_member(url, entry)
            payload = _json_payload(content, str(entry["filename"]))
        except (HTTPError, URLError, OSError, RuntimeError, ValueError, zipfile.BadZipFile, zlib.error) as exc:
            manifests.append({"match_id": int(row.match_id), "format": fmt, "role": row.pilot_role,
                "external_file_status": "download_failed", "download_error": f"{type(exc).__name__}: {exc}",
                "archive_url": url, "archive_member": entry["filename"], "retrieved_utc": retrieval,
                "license": CRICSHEET_LICENSE, "sha256": "", "candidate_cricsheet_id": ids[0], **lookup_provenance})
            continue
        digest = hashlib.sha256(content).hexdigest()
        filename = Path(str(entry["filename"])).name
        local_path = MATCH_DIR / filename
        local_path.write_bytes(content)
        payloads[int(row.match_id)] = payload
        identity = _metadata_identity(row, payload)
        manifests.append({"match_id": int(row.match_id), "format": fmt, "role": row.pilot_role,
            "external_file_status": "downloaded", "archive_url": url, "archive_member": entry["filename"],
            "retrieved_utc": retrieval, "license": CRICSHEET_LICENSE, "sha256": digest,
            "local_filename": filename, "candidate_cricsheet_id": ids[0], **lookup_provenance, **identity})

    # The people and venue registers are the published ID crosswalk needed for identity checks.
    register_specs = [
        ("people.csv", "https://cricsheet.org/register/people.csv"),
        ("venues.csv", "https://cricsheet.org/register/venues.csv"),
    ]
    reg_manifest = []
    for name, url in register_specs:
        data = _fetch_whole_file(url)
        path = EXTERNAL / "register" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        reg_manifest.append({"file": f"register/{name}", "source_url": url, "retrieved_utc": retrieval,
            "license": CRICSHEET_LICENSE, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})

    pd.DataFrame(manifests).to_csv(EXTERNAL / "pilot_selection_and_downloads.csv", index=False)
    pd.DataFrame(reg_manifest).to_csv(EXTERNAL / "register_manifest.csv", index=False)
    attribution = (
        "Source: Cricsheet.org, individual selected JSON match files and Cricsheet Registers. "
        "JSON/register data licensed under ODC-BY 1.0. Changes: none to downloaded originals. "
        "Retrieved only pilot JSON ZIP members with HTTP byte ranges on " + retrieval + ". "
        "Cricsheet Ashwin per-match info CSV members were read in memory to map local fixtures to numeric JSON member IDs; no CSV members were extracted to disk. "
        "ZIP archives were not stored. Match JSON originals are under matches/."
    )
    (EXTERNAL / "ATTRIBUTION.txt").write_text(attribution + "\n", encoding="utf-8")
    status_counts = pd.Series([x["external_file_status"] for x in manifests]).value_counts().to_dict()
    return {"selected": len(pilot), "downloaded_json": int(status_counts.get("downloaded", 0)),
            "unresolved_no_match_index_entry": int(status_counts.get("unresolved_no_match_index_entry", 0)),
            "ambiguous_match_index_candidates": int(status_counts.get("ambiguous_match_index_candidates", 0)),
            "json_member_missing_from_archive": int(status_counts.get("json_member_missing_from_archive", 0)),
            "ambiguous_json_archive_members": int(status_counts.get("ambiguous_json_archive_members", 0)),
            "download_failed": int(status_counts.get("download_failed", 0)),
            "retrieved_utc": retrieval}


def _fetch_whole_file(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "RR-Pressure-X-reconciliation/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        if response.status != 200:
            raise RuntimeError(f"Unable to retrieve required register: HTTP {response.status} {url}")
        return response.read()


def _make_crosswalk(local: pd.DataFrame, payloads: dict[int, dict[str, object]], people: pd.DataFrame) -> tuple[pd.DataFrame, dict[tuple[int, int], str]]:
    local_rows = local[local.match_id.isin(payloads)].copy()
    id_cols = ["striker_id", "non_striker_id", "bowler_id", "dismissed_player_id"]
    player_rows = []
    state = {}
    key_cols = [c for c in people.columns if c.startswith("key_")]
    for match_id, payload in payloads.items():
        match_local = local_rows[local_rows.match_id.eq(match_id)]
        registry = _registry_people(payload)
        registry_ids = set(registry.values())
        eligible = people[people["identifier"].astype(str).isin(registry_ids)].copy()
        for col in key_cols:
            eligible[col] = eligible[col].astype("string").str.strip()
        ids = sorted(set(int(x) for col in id_cols for x in match_local[col].dropna().unique()))
        for player_id in ids:
            exact_matches = []
            for _, person in eligible.iterrows():
                found_keys = [col for col in key_cols if str(person[col]) == str(player_id)]
                if found_keys:
                    exact_matches.append((person, found_keys))
            if len(exact_matches) == 1:
                person, found_keys = exact_matches[0]
                csid = str(person["identifier"])
                status = "candidate_exact_register_id_namespace_unconfirmed"
                state[(match_id, player_id)] = status
                external_name = str(person.get("name", ""))
                key_columns = ";".join(found_keys)
                candidates = csid
            elif len(exact_matches) > 1:
                status = "ambiguous_exact_id_maps_to_multiple_register_people"
                state[(match_id, player_id)] = "ambiguous"
                external_name = ""
                key_columns = ";".join(sorted({col for _, cols in exact_matches for col in cols}))
                candidates = ";".join(str(person["identifier"]) for person, _ in exact_matches)
            else:
                status, external_name, key_columns, candidates = "unresolved_no_exact_external_id_match", "", "", ""
                state[(match_id, player_id)] = "unresolved"
            official_names = local_rows[local_rows.match_id.eq(match_id)]
            name_col_values = []
            for id_col, name_col in [("striker_id", "striker_name"), ("non_striker_id", "non_striker_name"), ("bowler_id", "bowler_name")]:
                name_col_values.extend(official_names.loc[official_names[id_col].eq(player_id), name_col].dropna().astype(str).tolist())
            official_name = max(set(name_col_values), key=name_col_values.count) if name_col_values else ""
            # Names appear only as a manual-review hint. They never create the crosswalk.
            name_candidates = people.loc[people["name"].astype("string").str.casefold().eq(official_name.casefold()), "identifier"].astype(str).tolist() if official_name else []
            if not exact_matches and name_candidates:
                status = "unresolved_name_candidate_only_no_join"
                state[(match_id, player_id)] = "unresolved"
                candidates = ";".join(name_candidates)
            player_rows.append({"match_id": match_id, "official_player_id": player_id, "official_display_name": official_name,
                "external_registry_identifier": candidates, "external_display_name": external_name,
                "external_key_column": key_columns, "identity_status": status,
                "name_candidate_ids_for_manual_review": ";".join(name_candidates),
                "namespace_confirmation": "unresolved: official player_id system is undocumented"})
    return pd.DataFrame(player_rows), state


def _match_result_status(local: pd.Series, payload: dict[str, object]) -> str:
    winner_id = local.get("win_team_id")
    external_winner = str((payload.get("info", {}).get("outcome") or {}).get("winner", ""))
    if pd.isna(winner_id) or not external_winner:
        return "unresolved_no_decisive_winner"
    teams = [str(x) for x in payload.get("info", {}).get("teams", [])]
    # Restrict candidate to the two teams in this identity-checked match; this is a result check, not a player join.
    selected_team = str(local.get("home_team")) if int(winner_id) == int(local.get("home_team_id")) else str(local.get("away_team")) if int(winner_id) == int(local.get("away_team_id")) else ""
    source_winner = next((x for x in teams if _team_key(x) == _team_key(selected_team)), "")
    return "exact" if source_winner and _team_key(source_winner) == _team_key(external_winner) else "mismatch"


def _aggregate_innings(payload: dict[str, object]) -> list[dict[str, object]]:
    summaries = []
    for number, innings in enumerate(payload.get("innings", []), start=1):
        deliveries = [d for over in innings.get("overs", []) for d in over.get("deliveries", [])]
        sums = [d.get("runs", {}) for d in deliveries]
        totals = sum(int(s.get("total", 0)) for s in sums)
        bat_runs = sum(int(s.get("batter", s.get("batsman", 0))) for s in sums)
        extras = sum(int(s.get("extras", 0)) for s in sums)
        penalties = innings.get("penalty_runs", {}) or {}
        total = totals + int(penalties.get("pre", 0)) + int(penalties.get("post", 0))
        wicket_events = [w for d in deliveries for w in (d.get("wickets", []) or [])]
        wkts = sum(_team_wickets_lost([w]) for w in wicket_events)
        bowler_credited_wkts = sum(_bowler_credited_wickets([w]) for w in wicket_events)
        legal = sum(not bool(int((d.get("extras", {}) or {}).get("wides", 0) or 0) or int((d.get("extras", {}) or {}).get("noballs", 0) or 0)) for d in deliveries)
        summaries.append({"innings": number, "team": str(innings.get("team", "")), "deliveries": len(deliveries),
            "runs_total_events": totals, "innings_penalty_runs": int(penalties.get("pre", 0)) + int(penalties.get("post", 0)),
            "innings_total_candidate": total, "batter_runs_sum": bat_runs, "extras_sum": extras,
            "wickets": wkts, "wicket_event_markers": len(wicket_events),
            "bowler_credited_wickets_candidate": bowler_credited_wkts,
            "legal_balls_candidate": legal, "target": (innings.get("target") or {}).get("runs"),
            "target_overs": (innings.get("target") or {}).get("overs"), "super_over": bool(innings.get("super_over", False))})
    return summaries


def run_reconciliation() -> dict[str, object]:
    matches, competitions, balls, states = _load_local()
    if not (EXTERNAL / "pilot_selection_and_downloads.csv").exists():
        raise FileNotFoundError("Run `python -m src.cricsheet_pilot --download` first")
    pilot = matches[matches.match_id.isin(PILOT_IDS)].merge(competitions, on="comp_id", validate="many_to_one")
    download_manifest = pd.read_csv(EXTERNAL / "pilot_selection_and_downloads.csv", keep_default_na=False)
    people = pd.read_csv(EXTERNAL / "register" / "people.csv", low_memory=False, dtype="string")
    venues_path = EXTERNAL / "register" / "venues.csv"
    venues = pd.read_csv(venues_path, low_memory=False, dtype="string") if venues_path.exists() else pd.DataFrame()
    local_norm = balls.merge(states[["match_id", "innings", "sequence", "team_runs_delta", "legal_delivery", "legal_delivery_status",
        "score_known", "innings_final_score_if_known", "innings_balls_limit"]],
        left_on=["match_id", "innings", "innings_ball_num"], right_on=["match_id", "innings", "sequence"], how="left", validate="one_to_one")
    payloads = {}
    for record in download_manifest.to_dict("records"):
        if record.get("external_file_status") == "downloaded":
            path = MATCH_DIR / str(record["local_filename"])
            payloads[int(record["match_id"])] = json.loads(path.read_text(encoding="utf-8"))
    local_match_rows = local_norm[local_norm.match_id.isin(payloads)]
    crosswalk, state_map = _make_crosswalk(local_match_rows, payloads, people)
    crosswalk.to_csv(REPORTS / "player_crosswalk.csv", index=False)
    delivery_frames = []
    match_records, decisions = [], []
    summary_map = {}
    manifest_map = download_manifest.set_index("match_id").to_dict("index")
    for _, row in pilot.iterrows():
        match_id = int(row.match_id)
        manifest = manifest_map.get(match_id, {})
        payload = payloads.get(match_id)
        raw_local = local_norm[local_norm.match_id.eq(match_id)].copy()
        status = str(manifest.get("external_file_status", "not_found_in_archive"))
        match_identity = "not_comparable"
        identity = {}
        event_frame = pd.DataFrame()
        if payload is not None:
            identity = _metadata_identity(row, payload)
            match_identity = "exact" if identity["date_match"] and identity["teams_match"] and identity["format_match"] and identity["competition_family_match"] else "mismatch"
            event_frame = _flatten_deliveries(payload)
            match_del = compare_deliveries(match_id, local_norm, event_frame, state_map)
            delivery_frames.append(match_del)
            paired = match_del[match_del["row_alignment_status"].eq("aligned")]
            row_alignment = "exact" if len(paired) == len(match_del) and len(raw_local) == len(event_frame) else "mismatch"
            batter_runs_status = "exact" if not paired.empty and paired["batter_runs_status"].eq("exact").all() and len(paired) == len(raw_local) == len(event_frame) else "mismatch" if paired["batter_runs_status"].eq("mismatch").any() else "partial"
            extras_amounts_status = "unavailable_official_extra_amounts" if raw_local["extras_type"].notna().any() else "exact_zero_extras_only" if not event_frame.extras_keys.astype(bool).any() else "unresolved"
            total_runs_status = "unavailable_official_delivery_total"
            legal_status = "exact" if paired["legal_delivery_status"].eq("exact").all() and len(paired) == len(raw_local) == len(event_frame) else "partial_or_mismatch"
            wicket_status = "exact_event_flags_only" if paired["wicket_count_status"].eq("exact").all() else "mismatch"
            innings_totals_status = "unresolved_no_official_innings_totals"
            target_status = "unresolved_no_comparable_local_target" if pd.isna(row.get("revised_target")) else "not_all_innings_targets_present_in_local_source"
            bowling_status = "unresolved_no_official_bowling_figures"
            result_status = _match_result_status(row, payload)
            players = crosswalk[crosswalk.match_id.eq(match_id)]
            player_status = "exact" if not players.empty and players.identity_status.eq("accepted_exact_namespace").all() else "unresolved_player_id_namespace_or_mapping"
            venue_status = "exact" if identity.get("venue_id_match") else "unresolved_opaque_local_venue_id"
            genuine_mismatches = int((match_del[["batter_runs_status", "legal_delivery_status", "wicket_count_status"]] == "mismatch").sum().sum())
            decision, reason = accept_match({"external_file_status": status, "match_identity_status": match_identity,
                "genuine_mismatch_count": genuine_mismatches, "player_identity_status": player_status,
                "venue_identity_status": venue_status, "delivery_sequence_status": row_alignment,
                "batter_runs_status": batter_runs_status, "extras_amounts_status": extras_amounts_status,
                "total_runs_status": total_runs_status, "legal_balls_status": legal_status,
                "wickets_status": wicket_status, "innings_totals_status": innings_totals_status,
                "target_status": target_status, "bowling_figures_status": bowling_status, "result_status": result_status})
            status_counts = match_del.delivery_reconciliation_status.value_counts().to_dict()
            rec_status = "mismatch" if genuine_mismatches or row_alignment == "mismatch" else "exact-match" if decision == "accepted" else "partial-match"
            inning_summaries = _aggregate_innings(payload)
            local_final = raw_local.groupby("innings")["innings_final_score_if_known"].last().dropna()
            local_final_map = {int(k): int(v) for k, v in local_final.items()}
            for inn in inning_summaries:
                inn["official_final_score_if_known"] = local_final_map.get(inn["innings"])
                inn["official_final_score_status"] = "exact" if inn["innings"] in local_final_map and inn["innings_total_candidate"] == local_final_map[inn["innings"]] else "unavailable_or_unverified"
        else:
            decision = "unresolved"
            unresolved_reasons = {
                "unresolved_no_match_index_entry": "No unique date/team candidate in the delivery metadata index; archive absence is not established",
                "ambiguous_match_index_candidates": "Multiple date/team candidates in metadata index; manual identity review required",
                "json_member_missing_from_archive": "Metadata index ID has no corresponding JSON member; source index disagreement requires review",
                "ambiguous_json_archive_members": "Multiple JSON members for one metadata ID; manual review required",
                "ambiguous_archive_members": "Multiple JSON archive members for the metadata ID; manual review required",
                "download_failed": "JSON retrieval or parsing failed; no values imputed",
            }
            reason = unresolved_reasons.get(status, "No verified Cricsheet JSON available for this match; no values imputed")
            rec_status = "unresolved"
            row_alignment = batter_runs_status = extras_amounts_status = total_runs_status = legal_status = wicket_status = "unresolved_no_external_events"
            innings_totals_status = target_status = bowling_status = result_status = "unresolved_no_external_record"
            player_status = venue_status = "unresolved_no_external_record"
            status_counts = {}
            inning_summaries = []
            genuine_mismatches = 0
        match_rec = {
            "official_match_id": match_id, "comp_id": int(row.comp_id), "competition": row.comp_name,
            "format": row.match_format, "season": row.season, "match_date": row.match_date,
            "home_team": row.home_team, "away_team": row.away_team, "venue_id": row.venue_id,
            "venue_country": row.venue_country, "local_result": row.result,
            "pilot_role": "control" if match_id in CONTROL_IDS else "missing_delivery_candidate",
            "official_local_delivery_rows": len(raw_local), "external_file_status": status,
            "external_filename": manifest.get("local_filename", ""), "external_source_url": manifest.get("archive_url", ""),
            "external_archive_member": manifest.get("archive_member", ""), "external_sha256": manifest.get("sha256", ""),
            "match_identity_status": match_identity, "match_reconciliation_status": rec_status,
            "delivery_sequence_status": row_alignment, "external_delivery_rows": len(event_frame),
            "aligned_deliveries": int(status_counts.get("exact_match", 0) + status_counts.get("partial_match", 0) + status_counts.get("mismatch", 0)),
            "delivery_exact_count": int(status_counts.get("exact_match", 0)), "delivery_partial_count": int(status_counts.get("partial_match", 0)),
            "delivery_mismatch_count": int(status_counts.get("mismatch", 0)), "delivery_unresolved_count": int(status_counts.get("unresolved", 0)),
            "batter_runs_status": batter_runs_status, "extras_amounts_status": extras_amounts_status,
            "total_runs_status": total_runs_status, "legal_balls_status": legal_status, "wickets_status": wicket_status,
            "innings_totals_status": innings_totals_status, "target_status": target_status,
            "bowling_figures_status": bowling_status, "result_status": result_status,
            "player_identity_status": player_status, "venue_identity_status": venue_status,
            "acceptance_decision": decision, "decision_reason": reason,
            "external_innings_summary_json": json.dumps(inning_summaries, ensure_ascii=False),
            **{f"external_{k}": v for k, v in identity.items()},
        }
        match_records.append(match_rec)
        summary_map[match_id] = match_rec
        for criterion, criterion_status, rationale in [
            ("Unique match identity", match_identity, "Date, team pair, format and event checked; venue crosswalk unavailable"),
            ("Delivery sequence", row_alignment, "Every local event aligned by innings/over/within-over position"),
            ("Player IDs", player_status, "Names are not used as a join key; official ID namespace unresolved"),
            ("Batter runs", batter_runs_status, "Local runs compared as batter-run candidate only"),
            ("Typed extras amounts", extras_amounts_status, "Official feed has category code but no complete per-type amount"),
            ("Delivery total runs", total_runs_status, "No official per-delivery total field"),
            ("Legal balls", legal_status, "Cricsheet derives from wide/no-ball keys; Overstep mapping inferred"),
            ("Wickets", wicket_status, "Wicket flags compared; player identity and dismissal type also required"),
            ("Innings totals", innings_totals_status, "Official final innings totals absent except 18 known innings globally"),
            ("Targets", target_status, "Official revised target field sparse and not comparable on most rows"),
            ("Bowling figures", bowling_status, "No independent official conceded-runs figures in local files"),
            ("Match result", result_status, "Winner/outcome compared where local winner ID is present"),
        ]:
            decisions.append({"official_match_id": match_id, "criterion": criterion, "status": criterion_status,
                "rationale": rationale, "match_decision": decision})
    if delivery_frames:
        deliveries_out = pd.concat(delivery_frames, ignore_index=True)
    else:
        deliveries_out = pd.DataFrame()
    match_df = pd.DataFrame(match_records)
    decisions_df = pd.DataFrame(decisions)
    match_df.to_csv(REPORTS / "match_reconciliation.csv", index=False)
    deliveries_out.to_csv(REPORTS / "delivery_reconciliation.csv", index=False)
    decisions_df.to_csv(REPORTS / "reconciliation_decisions.csv", index=False)
    (REPORTS / "cricsheet_pilot_report.md").write_text(_pilot_report(match_df, deliveries_out, crosswalk, download_manifest), encoding="utf-8")
    return {"selected_matches": len(match_df), "accepted": int(match_df.acceptance_decision.eq("accepted").sum()),
        "rejected": int(match_df.acceptance_decision.eq("rejected").sum()), "unresolved": int(match_df.acceptance_decision.eq("unresolved").sum()),
        "delivery_rows_compared": len(deliveries_out), "crosswalk_rows": len(crosswalk),
        "report": str(REPORTS / "cricsheet_pilot_report.md")}


def _pilot_report(matches: pd.DataFrame, deliveries: pd.DataFrame, crosswalk: pd.DataFrame, manifest: pd.DataFrame) -> str:
    counts = matches.acceptance_decision.value_counts().to_dict()
    statuses = matches.match_reconciliation_status.value_counts().to_dict()
    downloaded = int(manifest.external_file_status.eq("downloaded").sum())
    absent = int(manifest.external_file_status.eq("not_found_in_archive").sum())
    index_unresolved = int(manifest.external_file_status.eq("unresolved_no_match_index_entry").sum())
    missing = matches[matches.pilot_role.eq("missing_delivery_candidate")]
    recovered = int((missing.external_delivery_rows.fillna(0).astype(int) > 0).sum())
    exact_deliveries = int(deliveries.delivery_reconciliation_status.eq("exact_match").sum()) if not deliveries.empty else 0
    partial_deliveries = int(deliveries.delivery_reconciliation_status.eq("partial_match").sum()) if not deliveries.empty else 0
    mismatched_deliveries = int(deliveries.delivery_reconciliation_status.eq("mismatch").sum()) if not deliveries.empty else 0
    unresolved_crosswalk = int((~crosswalk.identity_status.eq("accepted_exact_namespace")).sum()) if not crosswalk.empty else 0
    return f"""# Phase 2F — Cricsheet Match Reconciliation Pilot

## Scope and provenance

Deterministic pilot selection: **{len(matches)} matches** ({int(matches.pilot_role.eq('missing_delivery_candidate').sum())} local matches with no delivery rows and {int(matches.pilot_role.eq('control').sum())} local-delivery controls), covering IPL and T20I. All local no-row candidates were included. Controls include regular event streams, DLS, and Super Over cases. Cricsheet originals are under `data/external/cricsheet/pilot/matches/`; the ZIP archives were never saved. Required People/Venue registers and per-file checksums are preserved under `data/external/cricsheet/pilot/register/` and in their manifests. No official CSV was edited and no missing official field was filled.

Attribution: Cricsheet JSON and registers, licensed under ODC-BY 1.0. See `data/external/cricsheet/pilot/ATTRIBUTION.txt` and register/file manifests for source URLs, retrieval timestamps, archive members, revisions and SHA-256 hashes.

## Match-level decisions

| decision | matches |
| --- | ---: |
| accepted | {counts.get('accepted', 0)} |
| rejected | {counts.get('rejected', 0)} |
| unresolved | {counts.get('unresolved', 0)} |

| reconciliation classification | matches |
| --- | ---: |
| exact-match | {statuses.get('exact-match', 0)} |
| partial-match | {statuses.get('partial-match', 0)} |
| mismatch | {statuses.get('mismatch', 0)} |
| unresolved | {statuses.get('unresolved', 0)} |

Acceptance used the Phase 2E zero-unexplained-difference gate. A delivery-aligned event stream alone is insufficient: player namespace, local venue ID, total-run/extras fields, independent innings totals, target, and bowling figures must also pass. The official source does not document the player-ID namespace and has no venue-name map. Where a Cricsheet player register key numerically matches an official ID, it is recorded only as an unconfirmed candidate; no name-only ID join is accepted. {unresolved_crosswalk} crosswalk rows remain unresolved/namespace-unconfirmed.

## Delivery comparison

Compared {len(deliveries):,} event-coordinate rows from downloaded control matches: {exact_deliveries:,} exact, {partial_deliveries:,} partial/structural, and {mismatched_deliveries:,} mismatched. The CSV records innings, over, within-over position, batter, bowler, batter runs, typed extras, total runs and wicket detail. A row is partial where the official side lacks per-type extra amounts or total runs; `runs` is compared only as a batter-run candidate. An inferred `Overstep`/no-ball mapping is labeled as inferred.

Structural differences are not treated as numerical disagreements: the official feed does not expose per-delivery team totals or complete extras amounts. Genuine mismatches (event sequence, compared batter-run value, legal status, wicket count or dismissal kind where comparable) are labeled separately and cause rejection. The detailed evidence is in `delivery_reconciliation.csv`.

## Missing-local-delivery recovery

All {len(missing)} pilot candidates with no local delivery rows were checked against the Cricsheet match metadata index. {recovered} had a downloaded Cricsheet JSON delivery file; {index_unresolved} had no candidate in the delivery metadata index and remain **unresolved** (that is not evidence the JSON archive lacks a record). {absent} were explicitly confirmed absent from a complete archive index. They are locally recorded as `Match Abandoned`. **Recovered delivery rows: {recovered}.** No missing values were backfilled.

## Metric feasibility

- **Batter runs:** Cricsheet provides an explicit per-delivery batter run amount. The pilot compares it with the official `runs` field. Acceptance still depends on a confirmed player ID crosswalk and a complete match reconciliation.
- **Balls faced / legal balls:** typed wides/no-balls support external derivation, including repeated actual-ball labels. Local extras ambiguity prevents complete agreement for the full feed; `other` remains unresolved. No global legality correction is made.
- **Innings totals / targets:** Cricsheet totals and target metadata can produce candidates, including innings penalties and Super Overs. The local tables lack independent innings totals/target metadata for most innings, so score reconciliation cannot pass the independent-scorecard gate.
- **Bowler runs conceded:** Cricsheet exposes typed extras sufficient to derive a candidate under cricket scoring rules. Independent bowling figures are absent locally in this pilot; no bowler-conceded run totals or economy metrics are declared verified.
- **Match state:** event-level Cricsheet fields are structurally sufficient to reconstruct a candidate state, but this pilot did not meet the all-fields acceptance gate. They are not merged into `data/processed/`, and verified-pressure coverage remains unchanged.

**Coverage impact:** no match was accepted, so validated score/pressure coverage gain is **zero**. The data model appears technically capable of improving metrics, but the present pilot cannot safely establish accepted values. The source-side event comparisons do not substitute for missing official totals, documented ID namespaces or a venue crosswalk.

## Structural differences and limitations

1. Official `runs` is a provisional batter-run candidate, not total delivery runs. `extras1_runs` is category-coded and `extras_2_runs` is not a complete typed amount.
2. Official `venue_id` has no documented namespace or local venue-name dimension, so Cricsheet's venue name cannot currently be joined authoritatively.
3. Official `player_id` namespace is undocumented. Register IDs and exact numeric key candidates are reported, but no player is joined on name alone and no guessed namespace is accepted.
4. Local innings totals and bowler figures are missing for most pilot innings, preventing independent reconciliation of totals and conceded runs.
5. Cricsheet archive absence means no record is supplied; it does not prove that the real-world match had no event or that another provider has no record.

## Reproduce

```powershell
.\\venv\\Scripts\\python.exe -m src.cricsheet_pilot --download
.\\venv\\Scripts\\python.exe -m src.cricsheet_pilot --reconcile
.\\venv\\Scripts\\python.exe -m pytest -q
```
"""


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--reconcile", action="store_true")
    args = parser.parse_args()
    if args.download:
        print(json.dumps(download_selected(), indent=2))
    if args.reconcile:
        print(json.dumps(run_reconciliation(), indent=2))
