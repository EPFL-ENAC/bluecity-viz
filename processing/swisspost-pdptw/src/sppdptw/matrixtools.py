"""OD-matrix diagnostics: units sniffing, comparison statistics, fits.

Everything works on plain numpy (no statsmodels dependency): the notebooks
must also run in minimal environments.
"""

import numpy as np
import pandas as pd

EARTH_RADIUS_M = 6_371_000


def haversine_m(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Great-circle distance in meters (vectorized)."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a))


def haversine_matrix(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Pairwise haversine distances (meters) between all coordinate pairs."""
    return haversine_m(
        lats[:, None], lons[:, None], lats[None, :], lons[None, :]
    )


def sniff_units(matrix: np.ndarray, hav_m: np.ndarray) -> pd.DataFrame:
    """Score what quantity/unit a matrix most plausibly is.

    Compares the implied ratio haversine / value against plausible ranges:

    - meters      -> ratio ~ 0.6–0.9   (1 / circuity, unitless)
    - kilometers  -> ratio ~ 600–900
    - seconds     -> ratio ~ 3–20      (m/s: urban driving speed)
    - minutes     -> ratio ~ 180–1200  (m/min)

    Returns one row per hypothesis with the fraction of OD pairs whose implied
    ratio falls inside the plausible range. The best hypothesis is the row
    with the highest score.
    """
    mask = (matrix > 0) & (hav_m > 100)  # ignore diagonal & quasi-identical points
    ratio = hav_m[mask] / matrix[mask]
    hypotheses = {
        "meters (distance)": (0.5, 1.0),
        "kilometers (distance)": (500, 1000),
        "seconds (time)": (3, 20),
        "minutes (time)": (180, 1200),
    }
    rows = [
        {
            "hypothesis": name,
            "plausible_range": rng,
            "score": float(((ratio >= rng[0]) & (ratio <= rng[1])).mean()),
            "median_ratio": float(np.median(ratio)),
        }
        for name, rng in hypotheses.items()
    ]
    return pd.DataFrame(rows).sort_values("score", ascending=False, ignore_index=True)


def asymmetry_stats(matrix: np.ndarray) -> dict:
    """Relative asymmetry |M - M.T| / max(M, M.T) over off-diagonal pairs."""
    m, mt = matrix, matrix.T
    mask = ~np.eye(len(m), dtype=bool) & ((m > 0) | (mt > 0))
    rel = np.abs(m - mt)[mask] / np.maximum(m, mt)[mask]
    return {
        "perfectly_symmetric": bool(np.allclose(m, mt)),
        "mean_rel_asymmetry": float(rel.mean()),
        "share_pairs_gt_10pct": float((rel > 0.10).mean()),
        "max_rel_asymmetry": float(rel.max()),
    }


def triangle_violations(matrix: np.ndarray, n_samples: int = 50_000, seed: int = 42) -> dict:
    """Rate of sampled (i,j,k) triples with M[i,k] > M[i,j] + M[j,k] (+1s tolerance)."""
    rng = np.random.default_rng(seed)
    n = len(matrix)
    i, j, k = rng.integers(0, n, (3, n_samples))
    ok = (i != j) & (j != k) & (i != k)
    i, j, k = i[ok], j[ok], k[ok]
    direct = matrix[i, k]
    detour = matrix[i, j] + matrix[j, k]
    viol = direct > detour + 1.0
    return {
        "n_triples": int(ok.sum()),
        "violation_rate": float(viol.mean()),
        "worst_excess_s": float((direct - detour).max()),
    }


def fit_through_origin(x: np.ndarray, y: np.ndarray) -> dict:
    """OLS fit y ≈ k·x. Returns k and R² (about the origin-constrained model)."""
    k = float((x * y).sum() / (x * x).sum())
    resid = y - k * x
    ss_res = float((resid**2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return {"k": k, "r2": 1 - ss_res / ss_tot}


def fit_affine(x: np.ndarray, y: np.ndarray) -> dict:
    """OLS fit y ≈ k·x + c with standard errors."""
    n = len(x)
    X = np.column_stack([x, np.ones(n)])
    coef, ss_res, *_ = np.linalg.lstsq(X, y, rcond=None)
    k, c = float(coef[0]), float(coef[1])
    resid = y - X @ coef
    sigma2 = float(resid @ resid) / (n - 2)
    cov = sigma2 * np.linalg.inv(X.T @ X)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return {
        "k": k,
        "c": c,
        "k_se": float(np.sqrt(cov[0, 0])),
        "c_se": float(np.sqrt(cov[1, 1])),
        "r2": 1 - float(resid @ resid) / ss_tot,
    }


def fit_loglog(x: np.ndarray, y: np.ndarray) -> dict:
    """OLS fit log y ≈ a + b·log x.

    b ≈ 1  -> pure multiplicative shift, factor k = exp(a)
    b ≠ 1  -> distance-dependent bias (short and long trips scale differently)
    """
    mask = (x > 0) & (y > 0)
    lx, ly = np.log(x[mask]), np.log(y[mask])
    out = fit_affine(lx, ly)
    return {
        "slope_b": out["k"],
        "slope_se": out["k_se"],
        "intercept_a": out["c"],
        "implied_k": float(np.exp(out["c"])),
        "r2": out["r2"],
    }


def breusch_pagan(x: np.ndarray, y: np.ndarray) -> dict:
    """Breusch–Pagan test of heteroscedasticity for the fit y ≈ k·x + c.

    Regresses squared residuals on x; LM statistic = n·R² ~ χ²(1).
    Small p-value -> residual variance depends on x (non-uniform error).
    """
    from scipy import stats

    aff = fit_affine(x, y)
    resid2 = (y - aff["k"] * x - aff["c"]) ** 2
    aux = fit_affine(x, resid2)
    lm = len(x) * max(aux["r2"], 0.0)
    return {"lm_stat": lm, "p_value": float(stats.chi2.sf(lm, df=1))}


def permutation_check(
    matrix: np.ndarray, reference: np.ndarray, n_samples: int = 500, seed: int = 0
) -> dict:
    """Detect a permuted/misaligned matrix.

    If per-pair values disagree wildly while the *sorted* value distributions
    match, the matrix rows/columns are likely permuted relative to the
    reference (the failure mode of building an OD matrix over ``list(set(...))``
    and consuming it in a different order).
    """
    rng = np.random.default_rng(seed)
    n = len(matrix)
    i, j = rng.integers(0, n, (2, n_samples))
    ok = i != j
    pairwise_corr = float(np.corrcoef(matrix[i[ok], j[ok]], reference[i[ok], j[ok]])[0, 1])
    dist_corr = float(
        np.corrcoef(np.sort(matrix, axis=None), np.sort(reference, axis=None))[0, 1]
    )
    return {
        "pairwise_corr": pairwise_corr,
        "sorted_distribution_corr": dist_corr,
        "suspect_permutation": bool(pairwise_corr < 0.5 and dist_corr > 0.95),
    }
