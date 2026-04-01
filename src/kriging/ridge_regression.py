from __future__ import annotations

from typing import Iterable

import numpy as np


def _as_2d_array(X) -> tuple[np.ndarray, list[str] | None]:
    """Convert feature input to a numeric 2D ndarray and optional feature names."""
    feature_names = None

    if hasattr(X, "to_numpy"):  # pandas DataFrame / Series
        arr = X.to_numpy(dtype=float)
        if hasattr(X, "columns"):
            feature_names = [str(c) for c in X.columns]
    else:
        arr = np.asarray(X, dtype=float)

    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2:
        raise ValueError("X must be a 2D table-like structure")
    if arr.shape[0] < 1 or arr.shape[1] < 1:
        raise ValueError("X must contain at least one row and one column")
    if not np.all(np.isfinite(arr)):
        raise ValueError("X contains non-finite values")

    return arr, feature_names


def _as_1d_array(y) -> np.ndarray:
    """Convert target input to a numeric 1D ndarray."""
    if hasattr(y, "to_numpy"):  # pandas Series / DataFrame column
        arr = y.to_numpy(dtype=float)
    else:
        arr = np.asarray(y, dtype=float)

    if arr.ndim == 2 and 1 in arr.shape:
        arr = arr.reshape(-1)
    if arr.ndim != 1:
        raise ValueError("y must be a 1D vector")
    if arr.shape[0] < 1:
        raise ValueError("y must contain at least one value")
    if not np.all(np.isfinite(arr)):
        raise ValueError("y contains non-finite values")

    return arr


def train_ridge(
    X,
    y,
    alpha: float = 1.0,
    fit_intercept: bool = True,
) -> dict:
    """
    Train ridge regression with closed-form solution.

    Parameters
    ----------
    X
        2D feature table (numpy array, list of lists, or pandas DataFrame).
    y
        1D target values.
    alpha
        L2 regularization strength. Must be >= 0.
    fit_intercept
        Whether to fit an intercept term.

    Returns
    -------
    dict
        Dictionary containing model parameters and training diagnostics.
    """
    X_arr, feature_names = _as_2d_array(X)
    y_arr = _as_1d_array(y)

    if X_arr.shape[0] != y_arr.shape[0]:
        raise ValueError("X and y must have the same number of rows")

    alpha = float(alpha)
    if alpha < 0:
        raise ValueError("alpha must be >= 0")

    n_samples, n_features = X_arr.shape

    if fit_intercept:
        x_mean = X_arr.mean(axis=0)
        y_mean = float(y_arr.mean())
        Xc = X_arr - x_mean
        yc = y_arr - y_mean
    else:
        x_mean = np.zeros(n_features, dtype=float)
        y_mean = 0.0
        Xc = X_arr
        yc = y_arr

    # Closed-form ridge: w = (X^T X + alpha I)^(-1) X^T y
    gram = Xc.T @ Xc
    reg = alpha * np.eye(n_features, dtype=float)
    coef = np.linalg.solve(gram + reg, Xc.T @ yc)

    intercept = float(y_mean - x_mean @ coef) if fit_intercept else 0.0
    y_pred = X_arr @ coef + intercept

    ss_res = float(np.sum((y_arr - y_pred) ** 2))
    ss_tot = float(np.sum((y_arr - y_arr.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan

    return {
        "model": "ridge",
        "alpha": alpha,
        "fit_intercept": bool(fit_intercept),
        "intercept": intercept,
        "coefficients": coef.tolist(),
        "n_features": int(n_features),
        "n_samples": int(n_samples),
        "feature_names": feature_names,
        "score_r2": r2,
        "training_predictions": y_pred.tolist(),
    }


def ridge_predict(model: dict, x: Iterable[float] | np.ndarray) -> float | np.ndarray:
    """
    Predict using a trained ridge model dictionary.

    Parameters
    ----------
    model
        Dictionary returned by train_ridge().
    x
        Feature vector (1D) for one prediction, or 2D array for batch predictions.

    Returns
    -------
    float or np.ndarray
        Predicted output value(s).
    """
    if model.get("model") != "ridge":
        raise ValueError("model dictionary is not a ridge model")

    coef = np.asarray(model["coefficients"], dtype=float)
    intercept = float(model.get("intercept", 0.0))

    x_arr = np.asarray(x, dtype=float)
    if x_arr.ndim == 1:
        if x_arr.shape[0] != coef.shape[0]:
            raise ValueError(
                f"x has {x_arr.shape[0]} features, expected {coef.shape[0]}"
            )
        return float(x_arr @ coef + intercept)

    if x_arr.ndim == 2:
        if x_arr.shape[1] != coef.shape[0]:
            raise ValueError(
                f"x has {x_arr.shape[1]} features, expected {coef.shape[0]}"
            )
        return x_arr @ coef + intercept

    raise ValueError("x must be a 1D feature vector or a 2D feature matrix")
