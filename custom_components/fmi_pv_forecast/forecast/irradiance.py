"""Irradiance transposition and reflection calculations.

Based on original code from fmidev/fmi-open-pv-forecast by Timo Salola.
Licensed under MIT License.
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd
from pvlib import irradiance, location, solarposition

from .panel import PanelArray

_LOGGER = logging.getLogger(__name__)


def get_clear_sky_irradiance(
    latitude: float,
    longitude: float,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
    timezone: str = "UTC",
    resolution_minutes: int = 60,
) -> pd.DataFrame:
    """Generate clear sky irradiance using PVlib.

    Args:
        latitude: Location latitude
        longitude: Location longitude
        start_time: Start of period
        end_time: End of period
        timezone: Timezone string
        resolution_minutes: Time resolution in minutes

    Returns:
        DataFrame with time, dni, dhi, ghi columns
    """
    site = location.Location(latitude, longitude, tz=timezone)
    times = pd.date_range(
        start=start_time,
        end=end_time,
        freq=f"{resolution_minutes}min",
        tz=timezone,
    )

    clearsky = site.get_clearsky(times, model="ineichen")
    clearsky.insert(loc=0, column="time", value=clearsky.index)

    return clearsky


def transpose_irradiance_to_poa(
    df: pd.DataFrame,
    panel: PanelArray,
    latitude: float,
    longitude: float,
) -> pd.DataFrame:
    """Transpose DNI, DHI, GHI to Plane of Array irradiance.

    Uses Perez diffuse sky model for accurate transposition.

    Args:
        df: DataFrame with time, dni, dhi, ghi columns
        panel: Panel array configuration
        latitude: Location latitude
        longitude: Location longitude

    Returns:
        DataFrame with added poa_direct, poa_diffuse, poa_ground, poa_global columns
    """
    df = df.copy()

    # Get solar position for all times
    times = pd.DatetimeIndex(df["time"])
    solar_pos = solarposition.get_solarposition(times, latitude, longitude)

    # Extract angles
    solar_zenith = solar_pos["apparent_zenith"].values
    solar_azimuth = solar_pos["azimuth"].values

    # Transpose direct (beam) irradiance
    aoi = irradiance.aoi(panel.tilt, panel.azimuth, solar_zenith, solar_azimuth)
    df["aoi"] = aoi

    # Direct component on POA
    dni_values = df["dni"].values
    cos_aoi = np.cos(np.radians(aoi))
    cos_aoi = np.maximum(cos_aoi, 0)  # No negative contributions
    df["poa_direct"] = dni_values * cos_aoi

    # Diffuse component using Perez model
    dhi_values = df["dhi"].values
    ghi_values = df["ghi"].values
    dni_extra = irradiance.get_extra_radiation(times)

    # Handle edge cases where zenith > 90
    valid_zenith = np.minimum(solar_zenith, 89.9)

    try:
        poa_sky_diffuse = irradiance.perez(
            surface_tilt=panel.tilt,
            surface_azimuth=panel.azimuth,
            dhi=dhi_values,
            dni=dni_values,
            dni_extra=dni_extra,
            solar_zenith=valid_zenith,
            solar_azimuth=solar_azimuth,
            airmass=irradiance.airmass.get_relative_airmass(valid_zenith),
        )
        df["poa_diffuse"] = np.maximum(poa_sky_diffuse, 0)
    except Exception as e:
        _LOGGER.warning("Perez model failed, using isotropic: %s", e)
        # Fallback to isotropic model
        df["poa_diffuse"] = dhi_values * (1 + np.cos(np.radians(panel.tilt))) / 2

    # Ground reflected component
    albedo = df.get("albedo", panel.albedo)
    if isinstance(albedo, (int, float)):
        albedo = np.full(len(df), albedo)
    df["poa_ground"] = ghi_values * albedo * (1 - np.cos(np.radians(panel.tilt))) / 2

    # Total POA irradiance
    df["poa_global"] = df["poa_direct"] + df["poa_diffuse"] + df["poa_ground"]

    return df


def apply_reflection_losses(
    df: pd.DataFrame,
    panel: PanelArray,
) -> pd.DataFrame:
    """Apply Martin-Ruiz reflection model to POA irradiance.

    Based on: Chivelet & Ruiz (2001) - Calculation of PV modules angular losses

    Args:
        df: DataFrame with poa_direct, poa_diffuse, poa_ground, aoi columns
        panel: Panel array configuration

    Returns:
        DataFrame with poa_ref_cor (reflection-corrected POA) column
    """
    df = df.copy()

    # Martin-Ruiz model parameter (typical value for glass-covered modules)
    ar = 0.16

    # Angle of incidence modifier for direct
    aoi = df["aoi"].values
    cos_aoi = np.cos(np.radians(aoi))

    # IAM for direct beam
    # f_direct = 1 - exp(-cos(aoi)/ar) / (1 - exp(-1/ar))
    with np.errstate(divide="ignore", invalid="ignore"):
        iam_direct = np.where(
            cos_aoi > 0,
            1 - np.exp(-cos_aoi / ar) / (1 - np.exp(-1 / ar)),
            0,
        )

    # IAM for diffuse (approximate integrated value)
    iam_diffuse = 1 - np.exp(-1 / ar * (1 - 0.5 * (1 - np.cos(np.radians(panel.tilt)))))

    # IAM for ground-reflected (approximate)
    iam_ground = 1 - np.exp(-1 / ar * 0.5 * (1 + np.cos(np.radians(panel.tilt))))

    # Apply IAM to each component
    df["poa_direct_rc"] = df["poa_direct"] * iam_direct
    df["poa_diffuse_rc"] = df["poa_diffuse"] * iam_diffuse
    df["poa_ground_rc"] = df["poa_ground"] * iam_ground

    # Total reflection-corrected POA
    df["poa_ref_cor"] = df["poa_direct_rc"] + df["poa_diffuse_rc"] + df["poa_ground_rc"]

    # Ensure non-negative
    df["poa_ref_cor"] = df["poa_ref_cor"].clip(lower=0)

    return df


def estimate_panel_temperature(
    df: pd.DataFrame,
    panel: PanelArray,
    wind_speed: Optional[float] = None,
    air_temp: Optional[float] = None,
) -> pd.DataFrame:
    """Estimate panel temperature using King 2004 model.

    Args:
        df: DataFrame with poa_ref_cor, wind, T columns
        panel: Panel array configuration
        wind_speed: Override wind speed (m/s)
        air_temp: Override air temperature (°C)

    Returns:
        DataFrame with module_temp column
    """
    df = df.copy()

    # King model constants for open rack glass/cell/glass
    a = -3.56
    b = -0.075
    delta_t = 3

    # Get weather data
    if wind_speed is not None:
        wind = np.full(len(df), wind_speed)
    elif "wind" in df.columns:
        wind = df["wind"].values
    else:
        wind = np.full(len(df), 2.0)  # Default 2 m/s

    if air_temp is not None:
        temp = np.full(len(df), air_temp)
    elif "T" in df.columns:
        temp = df["T"].values
    else:
        temp = np.full(len(df), 20.0)  # Default 20°C

    # Get irradiance
    poa = df["poa_ref_cor"].values

    # King model: T_module = T_air + poa * exp(a + b*wind) + delta_t * poa/1000
    df["module_temp"] = temp + poa * np.exp(a + b * wind) + delta_t * poa / 1000

    return df
