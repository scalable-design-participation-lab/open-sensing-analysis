import numpy as np
import matplotlib.pyplot as plt
from typing import List
def compute_rmse(reference_series, test_series):
    """
    Calculate the Root Mean Square Error (RMSE) between two time series.

    Parameters:
    reference_series (np.ndarray): The reference time series data.
    test_series (np.ndarray): The test time series data to compare against the reference.

    Returns:
    float: The RMSE value.
    """
    reference_series = np.array(reference_series)
    test_series = np.array(test_series)
    if len(reference_series) != len(test_series):
        raise ValueError("Both time series must have the same length.")

    mse = np.mean((reference_series - test_series) ** 2)
    rmse = np.sqrt(mse)
    return rmse


def compute_correlation_coefficient(reference_series, test_series):
    """
    Calculate the Pearson correlation coefficient between two time series.

    Parameters:
    reference_series (np.ndarray): The reference time series data.
    test_series (np.ndarray): The test time series data to compare against the reference.

    Returns:
    float: The Pearson correlation coefficient.
    """
    reference_series = np.array(reference_series)
    test_series = np.array(test_series)
    if len(reference_series) != len(test_series):
        raise ValueError("Both time series must have the same length.")

    correlation_matrix = np.corrcoef(reference_series, test_series)
    correlation_coefficient = correlation_matrix[0, 1]
    return correlation_coefficient


def compute_mae(reference_series, test_series):
    """
    Calculate the Mean Absolute Error (MAE) between two time series.

    Parameters:
    reference_series (np.ndarray): The reference time series data.
    test_series (np.ndarray): The test time series data.

    Returns:
    float: The mean absolute error.
    """
    reference_series = np.array(reference_series)
    test_series = np.array(test_series)

    if len(reference_series) != len(test_series):
        raise ValueError("Both time series must have the same length.")

    return np.mean(np.abs(test_series - reference_series))


def compute_bias(reference_series, test_series):
    """
    Calculate the mean bias (mean error) between two time series.

    Parameters:
    reference_series (np.ndarray): The reference time series data.
    test_series (np.ndarray): The test time series data.

    Returns:
    float: The mean bias (positive means test > reference).
    """
    reference_series = np.array(reference_series)
    test_series = np.array(test_series)

    if len(reference_series) != len(test_series):
        raise ValueError("Both time series must have the same length.")

    return np.mean(test_series - reference_series)



def compute_linear_fit(reference_series, test_series, plot=False):
    """
    Fit a linear model: test_series = slope * reference_series + intercept.

    Parameters:
    reference_series (np.ndarray): The reference time series data.
    test_series (np.ndarray): The test time series data to compare against the reference.

    Returns:
    dict: Fit results with slope, intercept, r_value, and r_squared.
    """
    reference_series = np.array(reference_series, dtype=float).ravel()
    test_series = np.array(test_series, dtype=float).ravel()
    if len(reference_series) != len(test_series):
        raise ValueError("Both time series must have the same length.")
    if len(reference_series) == 0:
        raise ValueError("Both time series must contain at least one value.")

    design_matrix = np.column_stack([reference_series, np.ones(len(reference_series))])
    slope, intercept = np.linalg.lstsq(design_matrix, test_series, rcond=None)[0]

    r_value = np.nan
    if len(reference_series) > 1:
        r_value = np.corrcoef(reference_series, test_series)[0, 1]
    r_squared = r_value ** 2 if not np.isnan(r_value) else np.nan

    if plot:
        import matplotlib.pyplot as plt
        plt.scatter(reference_series, test_series, alpha=0.5)
        plt.plot(reference_series, slope * reference_series + intercept, color='red')
        plt.xlabel("Reference Series")
        plt.ylabel("Test Series")
        plt.title("Linear Fit")
        plt.show()

    return {
        "slope": slope,
        "intercept": intercept,
        "r_value": r_value,
        "r_squared": r_squared,
    }



def compute_deming_regression(
        test_series:List[float],
        reference_series:List[float],
        plot = True,
        width: int = 7,
        height: int = 4,
        xlabel: str = "Reference values",
        ylabel: str = "Test values",
        title: str = "Deming Regression",
        point_color: str = "#3198e3",
        line_color: str = "#e31985"
)->None:
    
    mean_x = np.mean(test_series)
    mean_y = np.mean(reference_series)
    covariance_matrix = np.cov(test_series, reference_series)
    s_xx = covariance_matrix[0, 0]
    s_yy = covariance_matrix[1, 1]
    s_xy = covariance_matrix[0, 1]
    

    beta_1 = (s_yy - s_xx + np.sqrt((s_yy - s_xx)**2 + 4*s_xy**2)) / (2*s_xy)
    beta_0 = mean_y - beta_1 * mean_x
    if not plot:
        return beta_0, beta_1
    
    fig, ax = plt.subplots(figsize=(width, height))
    ax.scatter(test_series, reference_series, color=point_color, alpha=0.6)
    x_vals = np.array(ax.get_xlim())
    y_vals = beta_0 + beta_1 * x_vals
    ax.plot(x_vals, y_vals, color=line_color, linewidth=2)
    ax.text(0, 1.2, f"y = {beta_1:.2f}x + {beta_0:.2f}", transform=ax.transAxes, fontsize=12, verticalalignment='top', horizontalalignment = "right")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)


    return beta_0, beta_1


