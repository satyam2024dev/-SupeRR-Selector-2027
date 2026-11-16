import asyncio

import httpx

from api.app import app



class ASGIClient:
    """Small sync wrapper over HTTPX ASGI transport; avoids deprecated TestClient/httpx path."""
    def _request(self, method, path, **kwargs):
        async def send():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.request(method, path, **kwargs)
        return asyncio.run(send())

    def get(self, path, **kwargs):
        return self._request("GET", path, **kwargs)

    def options(self, path, **kwargs):
        return self._request("OPTIONS", path, **kwargs)


client = ASGIClient()


def test_health_reports_source_artifact_availability():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["artifacts"]["overall_batter_top10"] is True


def test_overall_ranking_is_the_frozen_phase5g_artifact():
    response = client.get("/api/v1/rankings/batters/overall")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 10
    assert [row["rank"] for row in payload["records"]] == list(range(1, 11))
    assert [str(row["player_id"]) for row in payload["records"]] == [
        "25534", "25669", "3282", "6574", "27469", "167", "6819", "24887", "6272", "3635"
    ]
    assert payload["records"][0]["mean_within_format_percentile"] == 1.0


def test_supporting_rankings_are_format_bounded():
    assert client.get("/api/v1/rankings/batters/supporting?format=IPL").json()["count"] == 10
    assert client.get("/api/v1/rankings/batters/supporting?format=T20I").json()["count"] == 10
    assert client.get("/api/v1/rankings/batters/supporting?format=ODI").status_code == 422


def test_search_and_status_inputs_have_reasonable_length_bounds():
    assert client.get(f"/api/v1/players?query={'x' * 101}").status_code == 422
    assert client.get(f"/api/v1/players/compare?ids={'1' * 101}").status_code == 422
    assert client.get(f"/api/v1/auction/availability?status={'x' * 65}").status_code == 422


def test_overview_distinct_eligible_players_comes_from_stored_phase5c_rows():
    payload = client.get("/api/v1/overview").json()
    assert payload["eligible_batter_player_format_rows"] == 305
    assert payload["eligible_batter_distinct_players"] > 0


def test_ranked_player_without_exposure_still_has_only_stored_ranking_evidence():
    response = client.get("/api/v1/players/25534/profiles")
    assert response.status_code == 200
    payload = response.json()
    assert payload["player_id"] == "25534"
    assert payload["exposure"] == []
    assert payload["ranking_evidence"]["overall"][0]["player_name"] == "Chad Bowes"
    assert payload["ranking_evidence"]["overall"][0]["mean_within_format_percentile"] == 1.0


def test_bowling_evidence_does_not_claim_ranked_recommendations():
    payload = client.get("/api/v1/bowling/evidence").json()
    assert payload["competition_ready"] == 0
    assert payload["exploratory_profiles"] == 414
    assert payload["ranked_recommendations_supported"] is False
    metrics = {row["metric"] for row in payload["metric_audit"]}
    assert "economy rate" in metrics
    assert "verified chase pressure exposure" in metrics
    assert "not supported" in payload["limitations_report"].casefold()


def test_auction_targets_are_status_gated_and_overlay_is_auditable():
    availability = client.get("/api/v1/auction/availability?role=batter").json()
    assert availability["overlay_present"] is True
    assert availability["as_of"] == "2026-11-13"
    targets = client.get("/api/v1/auction/targets").json()
    assert targets["count"] == 0
    assert targets["targets"] == []
    assert all(key in availability["records"][0] for key in ("source_url", "source_publication_date", "verification_date", "confidence_status", "explanation"))


def test_cors_is_restricted_to_local_frontend_origins():
    allowed = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    denied = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert denied.headers.get("access-control-allow-origin") is None


def test_comparison_returns_existing_profiles_without_recomputing():
    candidates = client.get("/api/v1/players?format=IPL&role=batter&limit=2").json()["records"]
    ids = ",".join(str(row["player_id"]) for row in candidates[:2])
    response = client.get(f"/api/v1/players/compare?ids={ids}&format=IPL")
    assert response.status_code == 200
    payload = response.json()
    assert [row["player_id"] for row in payload["records"]] == [str(row["player_id"]) for row in candidates[:2]]
    assert payload["format"] == "IPL"
    assert all(row["exposure"] for row in payload["records"])
    assert all("ranking_evidence" in row for row in payload["records"])
    assert client.get("/api/v1/players/compare?ids=25534").status_code == 422


def test_comparison_returns_exact_stored_phase5c_scores_for_selected_eligible_players():
    ranking = client.get("/api/v1/rankings/batters?format=IPL&limit=2").json()["records"]
    assert len(ranking) == 2
    ids = ",".join(str(row["player_id"]) for row in ranking)
    compared = client.get(f"/api/v1/players/compare?ids={ids}&format=IPL").json()["records"]
    assert [row["player_id"] for row in compared] == [str(row["player_id"]) for row in ranking]
    for expected, actual in zip(ranking, compared):
        stored = next(row for row in actual["ranking_evidence"] if row["format"] == "IPL")
        assert stored["rank"] == expected["rank"]
        assert stored["score"] == expected["score"]


def test_comparison_candidates_are_exact_phase5c_eligible_rank_rows():
    rankings = client.get("/api/v1/rankings/batters?format=T20I&limit=10").json()["records"]
    candidates = client.get("/api/v1/players/comparison-candidates?format=T20I&limit=10").json()
    assert candidates["eligible_only"] is True
    assert [row["player_id"] for row in candidates["records"]] == [str(row["player_id"]) for row in rankings]
    assert all(row["performance_eligible"] is True for row in candidates["records"])
    assert all(row["ranking_evidence"]["score"] == ranking["score"] for row, ranking in zip(candidates["records"], rankings))


def test_auction_target_endpoint_requires_performance_eligibility_and_official_pool_status(monkeypatch):
    from api import app as module

    rows = [
        {"player_id": "1", "player_name": "Registered eligible", "candidate_role": "batter", "performance_eligible": True, "ipl_2027_status": "officially_registered_for_auction", "performance_rank_ipl": 1, "source_url": "https://example.org/official", "verification_date": "2026-11-13"},
        {"player_id": "2", "player_name": "Released only", "candidate_role": "batter", "performance_eligible": True, "ipl_2027_status": "released_by_another_franchise_pending_registration"},
        {"player_id": "3", "player_name": "Exploratory bowler", "candidate_role": "bowler", "performance_eligible": True, "ipl_2027_status": "included_in_final_auction_register"},
        {"player_id": "4", "player_name": "Unqualified registered", "candidate_role": "batter", "performance_eligible": False, "ipl_2027_status": "included_in_final_auction_register"},
        {"player_id": "5", "player_name": "Unknown", "candidate_role": "batter", "performance_eligible": True, "ipl_2027_status": "unknown_unverified"},
    ]
    monkeypatch.setattr(module, "_availability", lambda: rows)
    payload = client.get("/api/v1/auction/targets").json()
    assert [row["player_id"] for row in payload["targets"]] == ["1"]
    assert payload["targets"][0]["source_url"] == "https://example.org/official"
    assert payload["targets"][0]["verification_date"] == "2026-11-13"


def test_availability_role_and_status_filters_preserve_source_records(monkeypatch):
    from api import app as module

    row = {"player_id": "2", "candidate_role": "bowler", "ipl_2027_status": "traded_to_other_franchise", "source_url": "https://example.org/trade", "source_publication_date": "2026-10-10", "verification_date": "2026-11-13"}
    monkeypatch.setattr(module, "_availability", lambda: [row])
    response = client.get("/api/v1/auction/availability?role=bowler&status=traded_to_other_franchise")
    assert response.status_code == 200
    assert response.json()["records"] == [row]
