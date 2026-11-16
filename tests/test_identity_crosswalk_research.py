from src.identity_crosswalk_research import (
    normalize_name,
    resolve_player_candidate,
    resolve_venue_candidate,
)


def test_exact_name_is_verified_only_with_unique_match_register_id():
    result = resolve_player_candidate(
        "Sikandar Raza",
        [{"name": "Sikandar Raza", "registry_id": "person-1"}],
    )
    assert result["status"] == "verified"
    assert result["method"] == "exact_name_team_competition"


def test_initial_surname_alias_is_candidate_not_verified():
    result = resolve_player_candidate(
        "Nitish Rana",
        [{"name": "N Rana", "registry_id": "person-1"}],
    )
    assert result["status"] == "candidate"
    assert result["method"] == "initial_surname_alias_candidate"


def test_duplicate_external_exact_names_with_conflicting_ids_are_ambiguous():
    result = resolve_player_candidate(
        "Mandeep Singh",
        [
            {"name": "Mandeep Singh", "registry_id": "person-1"},
            {"name": "Mandeep Singh", "registry_id": "person-2"},
        ],
    )
    assert result["status"] == "ambiguous"
    assert len(result["candidates"]) == 2


def test_duplicate_local_name_identity_is_ambiguous_even_with_one_exact_match():
    result = resolve_player_candidate(
        "Alex Lee",
        [{"name": "Alex Lee", "registry_id": "person-1"}],
        local_duplicate=True,
    )
    assert result["status"] == "ambiguous"


def test_spelling_similarity_is_only_a_candidate():
    result = resolve_player_candidate(
        "Abhishek Porel",
        [{"name": "Abishek Porel", "registry_id": "person-1"}],
    )
    assert result["status"] == "candidate"
    assert result["method"] == "spelling_similarity_suggestion"


def test_exact_venue_register_name_needs_official_context_for_verified_local_id():
    register = [{
        "identifier": "venue-1",
        "name": "Arun Jaitley Stadium",
        "unique_name": "Arun Jaitley Stadium, Delhi",
    }]
    candidate = resolve_venue_candidate("7", "Arun Jaitley Stadium", register, context_unique=True)
    verified = resolve_venue_candidate(
        "7", "Arun Jaitley Stadium", register, context_unique=True,
        authoritative_source_url="https://official.example/scorecard",
    )
    assert candidate["status"] == "candidate"
    assert candidate["external_venue_id"] == "venue-1"
    assert verified["status"] == "verified"


def test_venue_spelling_alias_stays_candidate_even_with_fixture_context():
    register = [{
        "identifier": "venue-1",
        "name": "Punjab Cricket Association Stadium, Mohali, Chandigarh",
        "unique_name": "Punjab Cricket Association Stadium, Mohali, Chandigarh",
    }]
    result = resolve_venue_candidate(
        "79", "Punjab Cricket Association IS Bindra Stadium, Mohali, Chandigarh",
        register, context_unique=True,
        authoritative_source_url="https://official.example/scorecard",
    )
    assert result["status"] == "candidate"
    assert result["method"] == "venue_name_alias_candidate"


def test_ambiguous_venue_register_ids_are_not_forced():
    register = [
        {"identifier": "venue-1", "name": "Central Ground", "unique_name": "Central Ground"},
        {"identifier": "venue-2", "name": "Central Ground", "unique_name": "Central Ground 2"},
    ]
    result = resolve_venue_candidate("55", "Central Ground", register, context_unique=True)
    assert result["status"] == "ambiguous"


def test_name_normalization_is_not_fuzzy():
    assert normalize_name("R. Ashwin") == normalize_name("R Ashwin")
    assert normalize_name("Abishek Porel") != normalize_name("Abhishek Porel")
