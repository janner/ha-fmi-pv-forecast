"""PV output estimation using Huld 2010 model.

Based on original code from fmidev/fmi-open-pv-forecast by Timo Salola.
Licensed under MIT License.

Reference:
T. Huld, R. Gottschalg, H. G. Beyer, and M. Topič,
Mapping the performance of PV modules, effects of module type and
data averaging, Solar Energy, 84 324--338 (2010).
"""
import logging

import numpy as np
import pandas as pd

from .panel import PanelArray
from ..const import (
    HULD_K1,
    HULD_K2,
    HULD_K3,
    HULD_K4,
    HULD_K5,
    HULD_K6,
    HULD_MIN_EFFICIENCY,
)

_LOGGER = logging.getLogger(__name__)


def estimate_output(
    absorbed_radiation: float,
    panel_temp: float,
    rated_power_kw: float,
) -> float:
    """Estimate PV output using Huld 2010 model.

    Args:
        absorbed_radiation: Solar irradiance absorbed by m² of panel surface (W/m²)
        panel_temp: Estimated solar panel temperature (°C)
        rated_power_kw: System rated power in kW

    Returns:
        Estimated system output in watts
    """
    if absorbed_radiation < 0.1:
        return 0.0

    # Huld model parameters
    k1 = HULD_K1
    k2 = HULD_K2
    k3 = HULD_K3
    k4 = HULD_K4
    k5 = HULD_K5
    k6 = HULD_K6
    min_efficiency = HULD_MIN_EFFICIENCY

    # Normalized radiation and temperature difference
    nrad = absorbed_radiation / 1000.0
    t_diff = panel_temp - 25.0
    rated_power_w = rated_power_kw * 1000.0

    # Huld model efficiency calculation
    log_nrad = np.log(nrad)
    efficiency = (
        1
        + k1 * log_nrad
        + k2 * (log_nrad ** 2)
        + t_diff * (k3 + k4 * log_nrad + k5 * (log_nrad ** 2))
        + k6 * (t_diff ** 2)
    )

    # Apply minimum efficiency
    efficiency = max(efficiency, min_efficiency)

    # Calculate output
    output = rated_power_w * nrad * efficiency

    return output


def add_output_to_dataframe(
    df: pd.DataFrame,
    panel: PanelArray,
) -> pd.DataFrame:
    """Add power output column to DataFrame.

    Args:
        df: DataFrame with poa_ref_cor and module_temp columns
        panel: Panel array configuration

    Returns:
        DataFrame with output column (watts)
    """
    df = df.copy()

    # Ensure non-negative radiation
    df.loc[df["poa_ref_cor"] < 0, "poa_ref_cor"] = 0

    # Calculate output for each row
    def calc_output(row):
        if row["poa_ref_cor"] < 0.1:
            return 0.0
        return estimate_output(
            row["poa_ref_cor"],
            row["module_temp"],
            panel.rated_power,
        )

    df["output"] = df.apply(calc_output, axis=1)

    # Fill NaN values
    df["output"] = df["output"].fillna(0.0)

    return df


def calculate_daily_energy(
    df: pd.DataFrame,
    resolution_minutes: int = 60,
) -> dict[str, float]:
    """Calculate daily energy totals from power output.

    Args:
        df: DataFrame with time and output columns
        resolution_minutes: Time resolution in minutes

    Returns:
        Dictionary mapping date strings to kWh values
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["time"]).dt.date

    daily = df.groupby("date")["output"].sum()

    # Convert from W to kWh
    hours_per_interval = resolution_minutes / 60.0
    daily_kwh = (daily / 1000.0) * hours_per_interval

    return daily_kwh.to_dict()


def find_peak_power(
    df: pd.DataFrame,
    date: str = None,
) -> tuple[float, str]:
    """Find peak power and time for a given date.

    Args:
        df: DataFrame with time and output columns
        date: Date string (YYYY-MM-DD) or None for all data

    Returns:
        Tuple of (peak_power_watts, peak_time_iso)
    """
    df = df.copy()

    if date is not None:
        df["date"] = pd.to_datetime(df["time"]).dt.date.astype(str)
        df = df[df["date"] == date]

    if df.empty or df["output"].max() == 0:
        return 0.0, None

    peak_idx = df["output"].idxmax()
    peak_power = df.loc[peak_idx, "output"]
    peak_time = df.loc[peak_idx, "time"]

    # Convert to ISO format string
    if hasattr(peak_time, "isoformat"):
        peak_time_str = peak_time.isoformat()
    else:
        peak_time_str = str(peak_time)

    return float(peak_power), peak_time_str
