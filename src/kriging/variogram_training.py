from __future__ import annotations

from enum import Enum
from typing import Callable

import numpy as np
import matplotlib.pyplot as plt

class FitFunction(str, Enum):
    SPHERICAL = "spherical"
    EXPONENTIAL = "exponential"
    GAUSSIAN = "gaussian"


def _spherical(h: np.ndarray, nugget: float, sill: float, rng: float) -> np.ndarray:
    hr = h / rng
    inside = nugget + sill * (1.5 * hr - 0.5 * hr**3)
    return np.where(h <= rng, inside, nugget + sill)


def _exponential(h: np.ndarray, nugget: float, sill: float, rng: float) -> np.ndarray:
    return nugget + sill * (1.0 - np.exp(-h / rng))


def _gaussian(h: np.ndarray, nugget: float, sill: float, rng: float) -> np.ndarray:
    return nugget + sill * (1.0 - np.exp(-(h / rng) ** 2))


MODEL_FUNCS: dict[FitFunction, Callable[[np.ndarray, float, float, float], np.ndarray]] = {
    FitFunction.SPHERICAL: _spherical,
    FitFunction.EXPONENTIAL: _exponential,
    FitFunction.GAUSSIAN: _gaussian,
}

#MODEL_FUNCS = {FitFunction.EXPONENTIAL: _exponential}



def fit_variogram_model(
    points: list[tuple[float, float]],
    values: list[float],
) -> dict:
    """
    Fit a variogram model from sample locations and values.

    Returns a dictionary with:
    - model: selected model name
    - nugget, sill, range: fitted parameters
    - score_mse: MSE against experimental variogram bins
    - lag_centers: lag bin centers used for fitting
    - experimental_semivariance: empirical semivariances per lag
    - fitted_semivariance: model semivariances at lag_centers
    """
    if len(points) != len(values):
        raise ValueError("points and values must have the same length")
    if len(points) < 3:
        raise ValueError("at least 3 samples are required to fit a variogram")

    coords = np.asarray(points, dtype=float)
    vals = np.asarray(values, dtype=float)
    if coords.ndim != 2 or coords.shape[1] != 2:
        raise ValueError("points must be a list of (x, y) tuples")
    if not np.all(np.isfinite(coords)) or not np.all(np.isfinite(vals)):
        raise ValueError("points and values must be finite numbers")

    # Pairwise distances and semivariances (upper triangle only).
    diffs = coords[:, None, :] - coords[None, :, :]
    dists = np.sqrt(np.sum(diffs**2, axis=2))
    semivar = 0.5 * (vals[:, None] - vals[None, :]) ** 2
    iu = np.triu_indices(len(vals), k=1)
    pair_dists = dists[iu]
    pair_semivar = semivar[iu]

    max_dist = float(pair_dists.max())
    if max_dist <= 0:
        raise ValueError("all points are colocated; variogram is undefined")

    n_lags = int(np.clip(np.sqrt(len(pair_dists)), 8, 20))
    edges = np.linspace(0.0, max_dist, n_lags + 1)

    lag_centers: list[float] = []
    gamma_exp: list[float] = []
    for i in range(n_lags):
        lo, hi = edges[i], edges[i + 1]
        if i == n_lags - 1:
            mask = (pair_dists >= lo) & (pair_dists <= hi)
        else:
            mask = (pair_dists >= lo) & (pair_dists < hi)
        if np.any(mask):
            lag_centers.append((lo + hi) / 2.0)
            gamma_exp.append(float(np.mean(pair_semivar[mask])))

    if len(lag_centers) < 3:
        raise ValueError("not enough populated lag bins to fit variogram")

    h = np.asarray(lag_centers, dtype=float)
    g = np.asarray(gamma_exp, dtype=float)
    sample_var = float(np.var(vals))
    max_gamma = float(np.max(g))

    nugget_candidates = np.linspace(0.0, max(1e-12, max_gamma * 0.25), 8)
    sill_high = max(max_gamma * 2.0, sample_var * 2.0, 1e-12)
    sill_candidates = np.linspace(max(sill_high * 0.05, 1e-12), sill_high, 20)
    range_candidates = np.linspace(max_dist * 0.1, max_dist, 20)

    best_model: FitFunction | None = None
    best_params: tuple[float, float, float] | None = None
    best_mse = float("inf")

    for model_name, model_fn in MODEL_FUNCS.items():
        for nugget in nugget_candidates:
            for sill in sill_candidates:
                for rng in range_candidates:
                    pred = model_fn(h, float(nugget), float(sill), float(rng))
                    mse = float(np.mean((pred - g) ** 2))
                    if mse < best_mse:
                        best_mse = mse
                        best_model = model_name
                        best_params = (float(nugget), float(sill), float(rng))

    assert best_model is not None and best_params is not None
    nugget, sill, rng = best_params
    fitted = MODEL_FUNCS[best_model](h, nugget, sill, rng)

    return {
        "model": best_model.value,
        "nugget": nugget,
        "sill": sill,
        "range": rng,
        "score_mse": best_mse,
        "lag_centers": h.tolist(),
        "experimental_semivariance": g.tolist(),
        "fitted_semivariance": fitted.tolist(),
    }


def plot_variogram_fit(fit: dict, max_h: float | None = None, n: int = 300):
    model_enum = FitFunction(fit["model"])  # converts "spherical" -> FitFunction.SPHERICAL
    nugget = float(fit["nugget"])
    sill   = float(fit["sill"])
    rng    = float(fit["range"])

    model_fn = MODEL_FUNCS[model_enum]

    if max_h is None:
        max_h = max(fit["lag_centers"]) * 1.05
    h = np.linspace(0.0, max_h, n)

    gamma = model_fn(h, nugget, sill, rng)

    plt.figure()
    plt.plot(h, gamma, label=f'{model_enum.value} (n={nugget:.3g}, s={sill:.3g}, r={rng:.3g})', color = "blue")

    plt.scatter(fit["lag_centers"], fit["experimental_semivariance"], s=25, label="experimental")

    plt.xlabel("Lag distance h")
    plt.ylabel("Semivariance γ(h)")
    plt.legend()
    plt.tight_layout()
    plt.show()



import numpy as np
def ordinary_kriging_predict(
    points:List[tuple[float, float]], 
    values:List[float], fit, query_points:List[tuple[float, float]]) -> np.ndarray:
    coords = np.asarray(points, dtype=float)
    z = np.asarray(values, dtype=float)          
    q = np.asarray(query_points, dtype=float)    

    model = FitFunction(fit["model"])
    nugget = float(fit["nugget"])
    sill   = float(fit["sill"])
    rng    = float(fit["range"])
    gamma_fn = MODEL_FUNCS[model]

    n = coords.shape[0]

    # sample-sample distance matrix (n,n)
    D = np.sqrt(np.sum((coords[:, None, :] - coords[None, :, :])**2, axis=2))
    Gamma = gamma_fn(D, nugget, sill, rng)

    # ordinary kriging augmented matrix (n+1, n+1)
    A = np.zeros((n + 1, n + 1), dtype=float)
    A[:n, :n] = Gamma
    A[:n,  n] = 1.0
    A[n,  :n] = 1.0

    preds = np.empty(q.shape[0], dtype=float)

    for k in range(q.shape[0]):
        d0 = np.sqrt(np.sum((coords - q[k])**2, axis=1))   # (n,)
        b = gamma_fn(d0, nugget, sill, rng)

        rhs = np.zeros(n + 1, dtype=float)
        rhs[:n] = b
        rhs[n] = 1.0

        sol = np.linalg.solve(A, rhs)
        w = sol[:n]

        preds[k] = np.dot(w, z)

    return preds
