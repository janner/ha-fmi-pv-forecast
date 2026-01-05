"""FMI Open Data client for fetching weather forecast data.

Based on original code from fmidev/fmi-open-pv-forecast by Viivi Kallio and Timo Salola.
Licensed under MIT License.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from fmiopendata.wfs import download_stored_query

_LOGGER = logging.getLogger(__name__)


class FMIClient:
    """Client for fetching solar irradiance data from FMI Open Data."""

    COLLECTION_STRING = "fmi::forecast::harmonie::surface::point::multipointcoverage"
    PARAMETERS = [
        "Temperature",
        "RadiationGlobalAccumulation",
        "RadiationNetSurfaceSWAccumulation",
        "RadiationSWAccumulation",
        "WindSpeedMS",
        "TotalCloudCover",
    ]

    def __init__(self, latitude: float, longitude: float):
        """Initialize FMI client.

        Args:
            latitude: Location latitude
            longitude: Location longitude
        """
        self.latitude = latitude
        self.longitude = longitude
        self._last_fetch: Optional[datetime] = None
        self._cached_data: Optional[pd.DataFrame] = None

    @property
    def latlon(self) -> str:
        """Get lat,lon string for API."""
        return f"{self.latitude},{self.longitude}"

    def fetch_forecast(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Fetch irradiance forecast from FMI Open Data.

        Args:
            start_time: Start of forecast period (default: now)
            end_time: End of forecast period (default: start + 3 days)

        Returns:
            DataFrame with columns: time, dni, dhi, ghi, albedo, T, wind, cloud_cover
        """
        if start_time is None:
            start_time = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        if end_time is None:
            end_time = start_time + timedelta(days=3, minutes=-1)

        _LOGGER.debug(
            "Fetching FMI data for %s from %s to %s",
            self.latlon,
            start_time,
            end_time,
        )

        try:
            parameters_str = ",".join(self.PARAMETERS)
            snd = download_stored_query(
                self.COLLECTION_STRING,
                args=[
                    f"latlon={self.latlon}",
                    f"starttime={start_time}",
                    f"endtime={end_time}",
                    f"parameters={parameters_str}",
                ],
            )
            data = snd.data
        except Exception as err:
            _LOGGER.error("Failed to fetch FMI data: %s", err)
            raise

        # Convert nested dict structure to DataFrame
        data_list = []
        for time_a, location_data in data.items():
            location = list(location_data.keys())[0]
            values = location_data[location]

            data_list.append({
                "Time": time_a,
                "T": values["Air temperature"]["value"],
                "GHI_accum": values["Global radiation accumulation"]["value"],
                "NetSW_accum": values["Net short wave radiation accumulation at the surface"]["value"],
                "DirHI_accum": values["Short wave radiation accumulation"]["value"],
                "Wind speed": values["Wind speed"]["value"],
                "Total cloud cover": values["Total cloud cover"]["value"],
            })

        df = pd.DataFrame(data_list)
        df.set_index("Time", inplace=True)

        # Calculate instant from accumulated values
        diff = df.diff()
        df["GHI"] = diff["GHI_accum"] / 3600  # Convert from J/m² to W/m²
        df["NetSW"] = diff["NetSW_accum"] / 3600
        df["DirHI"] = diff["DirHI_accum"] / 3600

        # Calculate albedo (refl/ghi), refl=ghi-net
        df["albedo"] = (df["GHI"] - df["NetSW"]) / df["GHI"]
        df["albedo"] = df["albedo"].mask(~df["albedo"].between(0, 1))
        df["albedo"] = df["albedo"].fillna(df["albedo"].mean())

        # Calculate Diffuse horizontal from global and direct
        df["DHI"] = df["GHI"] - df["DirHI"]

        # Add solar zenith angle for DNI calculation
        df["time"] = df.index
        df["sza"] = self._calculate_solar_zenith(df["time"])

        # Calculate DNI from DirHI
        cos_sza = np.cos(np.radians(df["sza"]))
        cos_sza = np.maximum(cos_sza, 0.01)  # Avoid division by zero
        df["DNI"] = df["DirHI"] / cos_sza

        # Keep necessary parameters
        df = df[["DNI", "DHI", "GHI", "DirHI", "albedo", "T", "Wind speed", "Total cloud cover"]]
        df.columns = ["dni", "dhi", "ghi", "dir_hi", "albedo", "T", "wind", "cloud_cover"]

        # Add time column
        df.insert(loc=0, column="time", value=df.index)

        # Shift timestamps to time-interval centers
        df["time"] = df["time"] + timedelta(minutes=-30)
        df["time"] = df["time"].dt.tz_localize("UTC")

        # Clip negative values
        clip_columns = ["dni", "dhi", "ghi"]
        df[clip_columns] = df[clip_columns].clip(lower=0.0)
        df.replace(-0.0, 0.0, inplace=True)

        self._last_fetch = datetime.utcnow()
        self._cached_data = df

        _LOGGER.debug("Fetched %d rows of FMI data", len(df))
        return df

    def _calculate_solar_zenith(self, times: pd.Series) -> pd.Series:
        """Calculate solar zenith angle for given times.

        Simplified calculation for zenith angle.
        """
        from pvlib import solarposition

        # Convert to DatetimeIndex if needed
        if not isinstance(times.index, pd.DatetimeIndex):
            times_idx = pd.DatetimeIndex(times)
        else:
            times_idx = times.index

        # Use pvlib for accurate solar position
        solar_pos = solarposition.get_solarposition(
            times_idx,
            self.latitude,
            self.longitude,
        )
        return solar_pos["zenith"].values

    def get_last_fetch_time(self) -> Optional[datetime]:
        """Get time of last successful fetch."""
        return self._last_fetch

    def should_update(self) -> bool:
        """Check if we should fetch new data based on FMI update schedule.

        FMI updates every 3 hours starting from 00 UTC, with ~3h delay.
        """
        if self._last_fetch is None:
            return True

        now = datetime.utcnow()
        hours_since_fetch = (now - self._last_fetch).total_seconds() / 3600

        # Update at least every 3 hours
        if hours_since_fetch >= 3:
            return True

        # Check if we've crossed an FMI update boundary
        fmi_update_hours = [0, 3, 6, 9, 12, 15, 18, 21]
        delay_hours = 3  # FMI data is available ~3h after model run

        for hour in fmi_update_hours:
            update_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            available_time = update_time + timedelta(hours=delay_hours)

            if self._last_fetch < available_time <= now:
                return True

        return False
