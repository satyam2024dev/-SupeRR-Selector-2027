"""Sample-aware summaries of performance variation."""
import pandas as pd

def consistency_summary(values: pd.Series, min_observations: int = 3) -> dict[str, object]:
    """Return sample size, standard deviation and CV; small samples remain unclassified."""
    clean = pd.to_numeric(values, errors="coerce").dropna()
    n = len(clean)
    mean = float(clean.mean()) if n else None
    sd = float(clean.std(ddof=1)) if n > 1 else None
    cv = sd / abs(mean) if sd is not None and mean else None
    label = "insufficient observations" if n < min_observations else ("consistent" if cv is not None and cv <= 0.5 else "variable")
    return {"n": n, "mean": mean, "standard_deviation": sd, "coefficient_of_variation": cv, "classification": label}
