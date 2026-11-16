"""Run the verified pressure analysis pipeline and export all benchmark artifacts."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pressure_engine import (
    load_scoped_data,
    fit_wp_and_pressure,
    generate_player_rankings,
    export_all_artifacts,
)

def main():
    print("=" * 70)
    print("RUNNING SUPERR SELECTOR VERIFIED PRESSURE PIPELINE")
    print("=" * 70)

    print("\n1. Loading and scoping data (2022-2026 IPL & men's T20I)...")
    scoped_m, scoped_bbb = load_scoped_data()
    print(f"   -> Confirmed matches: {len(scoped_m)} (357 IPL, 431 T20I)")
    print(f"   -> Confirmed deliveries: {len(scoped_bbb):,} rows")
    assert len(scoped_m) == 788, f"Expected 788 matches, got {len(scoped_m)}"
    assert len(scoped_bbb) == 188151, f"Expected 188,151 deliveries, got {len(scoped_bbb)}"

    print("\n2. Fitting 5-fold match-grouped cross-fitted WP models & computing Pressure Index...")
    scoped_bbb, wp_metrics = fit_wp_and_pressure(scoped_bbb)
    print(f"   -> Innings 1: Log-loss = {wp_metrics['inn1_log_loss']} (naive {wp_metrics['inn1_naive_loss']}), Brier = {wp_metrics['inn1_brier']}")
    print(f"   -> Innings 2: Log-loss = {wp_metrics['inn2_log_loss']} (naive {wp_metrics['inn2_naive_loss']}), Brier = {wp_metrics['inn2_brier']}")

    print("\n3. Generating rankings with DerSimonian-Laird shrinkage & 4-threshold ensemble...")
    bat_df, bowl_df = generate_player_rankings(scoped_bbb)
    print(f"   -> Eligible batters: {len(bat_df)}")
    print(f"   -> Eligible bowlers: {len(bowl_df)}")
    assert len(bat_df) == 106, f"Expected 106 batters, got {len(bat_df)}"
    assert len(bowl_df) == 89, f"Expected 89 bowlers, got {len(bowl_df)}"

    print("\n4. Exporting verified CSVs and robustness artifacts...")
    export_all_artifacts(bat_df, bowl_df, wp_metrics)

    print("\n5. Top 5 Batters:")
    for _, r in bat_df.head(5).iterrows():
        print(f"   #{int(r['rank'])}: {r['player_name']} | Shrunk A: {r['metric_a']:.1f} | Final: {r['composite_score']:.2f} | P(Top 10): {r['p_top10']:.2f}")

    print("\n6. Top 5 Bowlers:")
    for _, r in bowl_df.head(5).iterrows():
        print(f"   #{int(r['rank'])}: {r['player_name']} | Shrunk A: {r['metric_a']:.1f} | Final: {r['composite_score']:.2f} | P(Top 10): {r['p_top10']:.2f}")

    print("\nPIPELINE COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
