"""Batting metrics from explicitly supplied aggregate counts."""
import numpy as np
import pandas as pd

def batting_average(runs: pd.Series, dismissals: pd.Series) -> pd.Series:
    """Runs per dismissal; not-outs must be excluded from dismissals upstream."""
    return pd.to_numeric(runs, errors="coerce").div(pd.to_numeric(dismissals, errors="coerce").replace(0, np.nan))

def strike_rate(runs: pd.Series, balls_faced: pd.Series) -> pd.Series:
    """Runs per 100 balls faced."""
    return 100 * pd.to_numeric(runs, errors="coerce").div(pd.to_numeric(balls_faced, errors="coerce").replace(0, np.nan))

def boundary_percentage(fours: pd.Series, sixes: pd.Series, runs: pd.Series) -> pd.Series:
    """Share of runs scored in boundaries, using 4s and 6s counts."""
    return (4 * fours + 6 * sixes).div(pd.to_numeric(runs, errors="coerce").replace(0, np.nan)) * 100

def runs_per_innings(runs: pd.Series, innings: pd.Series) -> pd.Series:
    """Runs divided by innings played."""
    return pd.to_numeric(runs, errors="coerce").div(pd.to_numeric(innings, errors="coerce").replace(0, np.nan))

def dot_ball_percentage(dot_balls: pd.Series, balls_faced: pd.Series) -> pd.Series:
    """Percentage of faced balls that are dot balls, if source fields exist."""
    return 100 * pd.to_numeric(dot_balls, errors="coerce").div(pd.to_numeric(balls_faced, errors="coerce").replace(0, np.nan))
