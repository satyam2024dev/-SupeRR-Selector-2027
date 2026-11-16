import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "../App";
import { overallTop10Fixture } from "./fixtures/overallTop10";

afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.pushState({}, "", "/"); });

function comparisonApi() {
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input); calls.push(path);
    let body: Record<string, unknown> = {};
    if (path.endsWith("/health")) body = { status: "ok" };
    if (path.includes("/players/comparison-candidates?")) body = { count: 3, source: "phase5c_batter_rankings.csv", records: [
      { player_id: "100", player_name: "Eligible One", role: "batter", format: "IPL", performance_eligible: true, pressure_matches: 4, baseline_matches: 5 },
      { player_id: "200", player_name: "Eligible Two", role: "batter", format: "IPL", performance_eligible: true, pressure_matches: 3, baseline_matches: 4 },
      { player_id: "300", player_name: "Limited Three", role: "batter", format: "IPL", performance_eligible: false },
    ] };
    if (path.includes("/players/compare?")) body = { source: "Phase5C artifacts", format: "IPL", records: [
      { player_id: "100", player_name: "Eligible One", exposure: [{ format: "IPL", pressure_observed_deliveries: 27, pressure_matches: 4, baseline_observed_deliveries: 42, baseline_matches: 5 }], profiles: { batter: [{ format: "IPL", cohort: "pressure", observed_deliveries: 27, ordinary_subset_balls: 23, ordinary_subset_strike_rate: 145.8 }, { format: "IPL", cohort: "baseline", observed_deliveries: 42, ordinary_subset_balls: 38, ordinary_subset_strike_rate: 128.9 }], bowler: [] }, ranking_evidence: [{ format: "IPL", score: 1.25, rank: 2 }] },
      { player_id: "200", player_name: "Eligible Two", exposure: [{ format: "IPL", pressure_observed_deliveries: 19, pressure_matches: 3, baseline_observed_deliveries: 32, baseline_matches: 4 }], profiles: { batter: [{ format: "IPL", cohort: "pressure", observed_deliveries: 19, ordinary_subset_balls: 18, ordinary_subset_strike_rate: 133.3 }, { format: "IPL", cohort: "baseline", observed_deliveries: 32, ordinary_subset_balls: 28, ordinary_subset_strike_rate: 117.8 }], bowler: [] }, ranking_evidence: [{ format: "IPL", score: 0.95, rank: 9 }] },
    ] };
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
  return calls;
}

describe("Phase 4 evidence pages", () => {
  it("compares eligible same-format players using stored API values", async () => {
    const calls = comparisonApi();
    window.history.pushState({}, "", "/comparison");
    render(<App />);
    await vi.dynamicImportSettled();
    expect(await screen.findByText("Eligible One")).toBeTruthy();
    expect(screen.queryByText("Limited Three")).toBeNull();
    fireEvent.click(screen.getByLabelText(/Eligible One/));
    fireEvent.click(screen.getByLabelText(/Eligible Two/));
    expect(await screen.findByText("1.25")).toBeTruthy();
    expect(screen.getByText("145.8")).toBeTruthy();
    expect(screen.getByText("128.9")).toBeTruthy();
    expect(calls.some((path) => path.includes("/players/compare?ids=100,200&format=IPL"))).toBe(true);
    expect(screen.getByText(/not verified psychological pressure/i)).toBeTruthy();
  });

  it("shows missing comparison fields without substituting values", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.endsWith("/health")) return new Response(JSON.stringify({ status: "ok" }));
      if (path.includes("/players/comparison-candidates?")) return new Response(JSON.stringify({ count: 2, records: [
        { player_id: "1", player_name: "One", role: "batter", format: "IPL", performance_eligible: true },
        { player_id: "2", player_name: "Two", role: "batter", format: "IPL", performance_eligible: true },
      ] }));
      if (path.includes("/players/compare?")) return new Response(JSON.stringify({ source: "test", format: "IPL", records: [
        { player_id: "1", player_name: "One", exposure: [], profiles: { batter: [], bowler: [] }, ranking_evidence: [] },
        { player_id: "2", player_name: "Two", exposure: [], profiles: { batter: [], bowler: [] }, ranking_evidence: [] },
      ] }));
      return new Response(JSON.stringify({}));
    }));
    window.history.pushState({}, "", "/comparison");
    render(<App />);
    await vi.dynamicImportSettled();
    fireEvent.click(await screen.findByLabelText(/One/));
    fireEvent.click(screen.getByLabelText(/Two/));
    await waitFor(() => expect(screen.getAllByText(/context values; profile detail unavailable/i).length).toBeGreaterThan(0));
    expect(screen.getAllByText("Not available").length).toBeGreaterThan(0);
  });

  it("keeps the bowling safeguard visible and does not invent a ranked list", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      const body = path.endsWith("/health") ? { status: "ok" } : path.endsWith("/bowling/evidence") ? {
        competition_ready: 0, exploratory_profiles: 414, ranked_recommendations_supported: false,
        metric_audit_source: "Phase 5H metric audit", eligibility_source: "Phase 5H eligibility",
        metric_audit: [
          { format: "IPL", metric: "ordinary dot rate", scope_row_coverage_pct: 94.04, verified_pressure_metric_value: 0.25, metric_numerator_or_observed_value: 31, metric_denominator: 42085, under_pressure_or_general: "Sparse verified chase comparison; no player meets both floors." },
          { format: "IPL", metric: "bowler-conceded runs", scope_row_coverage_pct: 0, under_pressure_or_general: "Unavailable in normal or pressure context; blocked." },
          { format: "IPL", metric: "verified chase pressure exposure", scope_row_coverage_pct: 0.07366, metric_numerator_or_observed_value: 31, metric_denominator: 42085, under_pressure_or_general: "Observed verified chase rows." },
          { format: "IPL", metric: "wicket/phase contextual proxy", scope_row_coverage_pct: 100, under_pressure_or_general: "Contextual batting-resource proxy only." },
        ],
        eligibility: [{ format: "IPL", metric: "ordinary_dot_rate", players_meeting_both_sides: 0, result: "No player meets both sides; floors unchanged." }],
      } : {};
      return new Response(JSON.stringify(body), { status: 200 });
    }));
    window.history.pushState({}, "", "/bowling");
    render(<App />);
    await vi.dynamicImportSettled();
    expect(await screen.findByText("414")).toBeTruthy();
    expect(screen.getByText("0")).toBeTruthy();
    expect(screen.getByText(/No bowling Top 10 is published/i)).toBeTruthy();
    expect(screen.getAllByText("Verified-chase cohort").length).toBeGreaterThan(0);
    expect(screen.getByText(/unavailable in normal or pressure context/i)).toBeTruthy();
  });

  it("shows availability evidence separately from the frozen performance list", async () => {
    const released = { player_id: "500", player_name: "Released Batter", candidate_role: "batter", performance_eligible: true, ipl_2027_status: "released_by_another_franchise_pending_registration", confidence_status: "official release; auction registration pending", previous_franchise: "Example franchise", source_url: "https://example.org/official-release", source_publication_date: "2026-11-12", status_reference_url: "https://example.org/status", status_reference_publication_date: "2026-11-12", process_timeline_source_url: "https://example.org/timeline", process_timeline_publication_date: "2026-11-10", verification_date: "2026-11-13", explanation: "Release is recorded; registration has not been verified." };
    const traded = { ...released, player_id: "600", player_name: "Traded Bowler", candidate_role: "bowler", performance_eligible: false, ipl_2027_status: "traded_to_other_franchise" };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      let body: Record<string, unknown> = {};
      if (path.endsWith("/health")) body = { status: "ok" };
      if (path.endsWith("/rankings/batters/overall")) body = { count: 10, records: overallTop10Fixture };
      if (path.endsWith("/auction/targets")) body = { overlay_present: true, as_of: "2026-11-13", count: 0, targets: [], empty_reason: "No qualified batter has official auction registration." };
      if (path.endsWith("/auction/availability")) body = { overlay_present: true, as_of: "2026-11-13", count: 2, source: "data/external/ipl_2027_player_availability.csv", records: [released, traded] };
      if (path.endsWith("/bowling/evidence")) body = { competition_ready: 0, exploratory_profiles: 414 };
      return new Response(JSON.stringify(body), { status: 200 });
    }));
    window.history.pushState({}, "", "/auction");
    render(<App />);
    await vi.dynamicImportSettled();
    expect(await screen.findByRole("heading", { name: "RR Auction Targets" })).toBeTruthy();
    expect(await screen.findByText("Released Batter")).toBeTruthy();
    expect((await screen.findAllByText("Traded Bowler")).length).toBeGreaterThan(0);
    expect(await screen.findByText(/No qualified batter has official auction registration/i)).toBeTruthy();
    expect(screen.getAllByRole("link", { name: "Availability source" })[0].getAttribute("href")).toBe("https://example.org/official-release");
    expect(await screen.findByText(/final auction register is not present/i)).toBeTruthy();
  });
});
