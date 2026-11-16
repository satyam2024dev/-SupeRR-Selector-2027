"""Bowling metrics from explicitly supplied aggregate counts."""
import numpy as np
import pandas as pd

def bowling_average(runs_conceded: pd.Series, wickets: pd.Series) -> pd.Series:
    """Runs conceded per wicket."""
    return pd.to_numeric(runs_conceded, errors="coerce").div(pd.to_numeric(wickets, errors="coerce").replace(0, np.nan))

def economy_rate(runs_conceded: pd.Series, legal_balls: pd.Series) -> pd.Series:
    """Runs conceded per six legal balls."""
    return pd.to_numeric(runs_conceded, errors="coerce").div(pd.to_numeric(legal_balls, errors="coerce").replace(0, np.nan)) * 6

def bowling_strike_rate(legal_balls: pd.Series, wickets: pd.Series) -> pd.Series:
    """Legal balls per wicket."""
    return pd.to_numeric(legal_balls, errors="coerce").div(pd.to_numeric(wickets, errors="coerce").replace(0, np.nan))

def wickets_per_match(wickets: pd.Series, matches: pd.Series) -> pd.Series:
    """Wickets per match played."""
    return pd.to_numeric(wickets, errors="coerce").div(pd.to_numeric(matches, errors="coerce").replace(0, np.nan))

def dot_ball_percentage(dot_balls: pd.Series, legal_balls: pd.Series) -> pd.Series:
    """Percentage of legal balls that are dots."""
    return 100 * pd.to_numeric(dot_balls, errors="coerce").div(pd.to_numeric(legal_balls, errors="coerce").replace(0, np.nan))
