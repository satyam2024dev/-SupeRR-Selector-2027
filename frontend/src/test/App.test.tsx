import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "../App";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function healthFetch() {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    let body: Record<string, unknown> = {};
    if (path.endsWith("/health")) body = { status: "ok" };
    if (path.endsWith("/overview")) body = { formats: [], matches_analyzed: 0, deliveries_analyzed: 0, eligible_batter_player_format_rows: 0, overall_batter_top10_count: 10, bowling: { competition_ready: 0, exploratory: 414 }, availability_snapshot: "" };
    if (path.includes("/rankings/batters")) body = { count: 0, records: [], source: "test response" };
    if (path.includes("/players")) body = { count: 0, records: [] };
    if (path.endsWith("/bowling/evidence")) body = { competition_ready: 0, exploratory_profiles: 414, ranked_recommendations_supported: false, metric_audit: [], eligibility: [], metric_audit_source: "test" };
    if (path.endsWith("/auction/targets")) body = { overlay_present: false, as_of: null, count: 0, targets: [], reason: "No overlay" };
    if (path.includes("/auction/availability")) body = { overlay_present: false, as_of: null, count: 0, records: [], reason: "No overlay" };
    if (path.endsWith("/methodology")) body = { source: "test", bowling_limitations_source: "test", report: "", bowling_limitations: "" };
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
}

describe("frontend foundation", () => {
  it("opens each of the seven navigable sections", async () => {
    healthFetch();
    render(<App />);
    await vi.dynamicImportSettled();
    expect(await screen.findByRole("heading", { name: /^overview$/i })).toBeTruthy();
    const routes = [
      ["Batter Rankings", /batter rankings/i],
      ["Player Discovery", /player discovery/i],
      ["Player Comparison", /player comparison/i],
      ["Bowling Intelligence", /bowling intelligence/i],
      ["RR Auction Targets", /rr auction targets/i],
      ["Methodology", /methodology/i],
      ["Overview", /^overview$/i],
    ] as const;
    for (const [link, heading] of routes) {
      fireEvent.click(screen.getAllByRole("link", { name: new RegExp(link, "i") })[0]);
      await vi.dynamicImportSettled();
      expect(await screen.findByRole("heading", { name: heading })).toBeTruthy();
    }
  });

  it("shows an API error state without substituting invented statistics", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("API unavailable"); }));
    render(<App />);
    await waitFor(() => expect(screen.getAllByText(/api unavailable/i).length).toBeGreaterThan(0));
    expect(screen.queryByText(/12,?345/)).toBeNull();
  });

  it("provides desktop and mobile navigation controls and responsive hooks", async () => {
    healthFetch();
    const { container } = render(<App />);
    expect(screen.getAllByRole("navigation", { name: /main navigation/i }).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /open navigation/i })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /open navigation/i }));
    expect(screen.getByLabelText(/mobile navigation/i)).toBeTruthy();
    expect(container.querySelector(".app-frame")).toBeTruthy();
  });
});
