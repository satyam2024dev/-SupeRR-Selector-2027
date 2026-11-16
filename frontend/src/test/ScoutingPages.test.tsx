import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "../App";
import { overallTop10Fixture } from "./fixtures/overallTop10";

afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.pushState({}, "", "/"); });

const profileResponse = {
  player_id: "25534",
  player_name: "Chad Bowes",
  source: "Phase 5G and existing profile artifacts",
  exposure: [],
  profiles: { batter: [] },
  ranking_evidence: { overall: [overallTop10Fixture[0]], formats: [] },
};

function stubApi() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    let body: Record<string, unknown> = {};
    if (path.endsWith("/health")) body = { status: "ok" };
    if (path.endsWith("/overview")) body = { formats: [{ format: "IPL", matches: 367, deliveries: 87687, seasons: "2022; 2023; 2024; 2025; 2026" }, { format: "T20I", matches: 470, deliveries: 106327, seasons: "2022; 2022/23; 2023; 2023/24; 2024; 2024/25; 2025; 2026" }], matches_analyzed: 837, deliveries_analyzed: 194014, eligible_batter_player_format_rows: 305, eligible_batter_distinct_players: 245, overall_batter_top10_count: 10, bowling: { competition_ready: 0, exploratory: 414 }, availability_snapshot: "2026-11-13" };
    if (path.endsWith("/rankings/batters/overall")) body = { source: "submission/phase5g_overall_batter_top10.csv", count: 10, records: overallTop10Fixture };
    if (path.includes("/rankings/batters/supporting")) body = { source: "supporting format artifact", count: 0, records: [] };
    if (path.endsWith("/auction/targets")) body = { overlay_present: true, as_of: "2026-11-13", count: 0, targets: [] };
    if (path.includes("/auction/availability")) body = { overlay_present: true, as_of: "2026-11-13", count: 107, records: [] };
    if (path.includes("/players/") && path.includes("/profiles")) body = profileResponse;
    else if (path.includes("/players")) body = { source: "player_exposure_summary.csv", count: 1, records: [{ player_id: "6574", player_name: "Alick Athanaze", role: "batter", format: "T20I", pressure_observed_deliveries: 2, pressure_matches: 1, baseline_observed_deliveries: 0, baseline_matches: 0, sufficient_evidence_for_future_pressure_comparison: false }] };
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("data-driven scouting pages", () => {
  it("renders the full authoritative overall order, IDs, and unrounded API scores", async () => {
    stubApi();
    render(<App />);
    fireEvent.click(screen.getAllByRole("link", { name: /batter rankings/i })[0]);
    await vi.dynamicImportSettled();
    await screen.findByRole("heading", { name: "Overall Batter Top 10" });
    await waitFor(() => expect(document.querySelectorAll(".player-evidence-card").length).toBe(10));

    const cards = Array.from(document.querySelectorAll(".player-evidence-card"));
    expect(cards.map((card) => card.querySelector(".player-card-name-wrap code")?.textContent)).toEqual(overallTop10Fixture.map((row) => row.player_id));
    expect(cards.map((card) => card.querySelector(".player-card-name-wrap h3")?.textContent)).toEqual(overallTop10Fixture.map((row) => row.player_name));
    expect(cards.map((card) => card.querySelector(".player-card-score strong")?.textContent)).toEqual(overallTop10Fixture.map((row) => String(row.mean_within_format_percentile)));
  });

  it("uses separate supporting endpoints for IPL and T20I filters without changing the overall response", async () => {
    const fetchMock = stubApi();
    render(<App />);
    fireEvent.click(screen.getAllByRole("link", { name: /batter rankings/i })[0]);
    await vi.dynamicImportSettled();
    await screen.findByRole("heading", { name: "Overall Batter Top 10" });
    fireEvent.click(screen.getByRole("button", { name: "IPL evidence" }));
    await screen.findByRole("heading", { name: "IPL supporting Top 10" });
    await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/rankings/batters/supporting?format=IPL"))).toBe(true));
    fireEvent.click(screen.getByRole("button", { name: "T20I evidence" }));
    await screen.findByRole("heading", { name: "T20I supporting Top 10" });
    await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/rankings/batters/supporting?format=T20I"))).toBe(true));
    fireEvent.click(screen.getByRole("button", { name: "Overall Top 10" }));
    await waitFor(() => expect(Array.from(document.querySelectorAll(".player-card-name-wrap code")).map((item) => item.textContent)).toEqual(overallTop10Fixture.map((row) => row.player_id)));
  });

  it("shows missing optional metrics without failing and opens a data-backed profile", async () => {
    const fetchMock = stubApi();
    window.history.pushState({}, "", "/discovery/25534?format=T20I");
    render(<App />);
    await vi.dynamicImportSettled();
    expect(await screen.findByRole("heading", { level: 2, name: "Chad Bowes" })).toBeTruthy();
    expect(screen.getByText(/No biography or personal details/i)).toBeTruthy();
    expect(screen.getByText(/no descriptive profile values/i)).toBeTruthy();
    expect(screen.getByText(/Overall mean within-format percentile/i)).toBeTruthy();
    expect(screen.getAllByText("Not available").length).toBeGreaterThan(0);
    expect(screen.getByText(/local ID 25534/)).toBeTruthy();
    expect(document.querySelector(".topbar-crumb strong")?.textContent).toBe("Player Discovery");
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/players?limit=100"))).toBe(false);
  });

  it("searches the existing player endpoint by name and shows source-backed exposure", async () => {
    const fetchMock = stubApi();
    render(<App />);
    fireEvent.click(screen.getAllByRole("link", { name: /player discovery/i })[0]);
    await vi.dynamicImportSettled();
    const search = await screen.findByRole("textbox", { name: /player name or id/i });
    fireEvent.change(search, { target: { value: "Alick Athanaze" } });
    expect(await screen.findByRole("heading", { name: "Alick Athanaze" })).toBeTruthy();
    expect(screen.getByText("2 deliveries · 1 matches")).toBeTruthy();
    await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/players?") && String(input).includes("query=Alick+Athanaze"))).toBe(true));
  });
});
