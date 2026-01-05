"""Main forecast engine that orchestrates the PV forecast calculation.

Based on original code from fmidev/fmi-open-pv-forecast.
Licensed under MIT License.
"""
import logging
from datetime import datetime, timedelta, date
from typing import Optional

import pandas as pd

from .panel import PanelArray, ForecastResult, AggregatedForecast
from .fmi_client import FMIClient
from .irradiance import (
    get_clear_sky_irradiance,
    transpose_irradiance_to_poa,
    apply_reflection_losses,
    estimate_panel_temperature,
)
from .output import add_output_to_dataframe, calculate_daily_energy, find_peak_power

_LOGGER = logging.getLogger(__name__)


class ForecastEngine:
    """Main engine for calculating PV forecasts."""

    def __init__(
        self,
        latitude: float,
        longitude: float,
        timezone: str = "UTC",
    ):
        """Initialize forecast engine.

        Args:
            latitude: Location latitude
            longitude: Location longitude
            timezone: Timezone string (e.g., "Europe/Helsinki")
        """
        self.latitude = latitude
        self.longitude = longitude
        self.timezone = timezone
        self.fmi_client = FMIClient(latitude, longitude)
        self._last_fmi_data: Optional[pd.DataFrame] = None
        self._last_update: Optional[datetime] = None

    def calculate_forecast(
        self,
        panels: list[PanelArray],
        use_fmi: bool = True,
    ) -> AggregatedForecast:
        """Calculate forecast for all panel arrays.

        Args:
            panels: List of panel array configurations
            use_fmi: Whether to use FMI weather data (True) or clear sky only (False)

        Returns:
            AggregatedForecast containing results for all arrays
        """
        _LOGGER.info("Calculating forecast for %d panel arrays", len(panels))

        # Fetch FMI data if needed
        if use_fmi:
            try:
                fmi_data = self.fmi_client.fetch_forecast()
                self._last_fmi_data = fmi_data
                self._last_update = datetime.utcnow()
            except Exception as e:
                _LOGGER.warning("Failed to fetch FMI data, using clear sky: %s", e)
                fmi_data = None
        else:
            fmi_data = None

        # Calculate forecast for each array
        results = []
        for panel in panels:
            try:
                result = self._calculate_array_forecast(panel, fmi_data)
                results.append(result)
            except Exception as e:
                _LOGGER.error("Failed to calculate forecast for %s: %s", panel.name, e)

        # Aggregate results
        return AggregatedForecast.from_results(results)

    def _calculate_array_forecast(
        self,
        panel: PanelArray,
        fmi_data: Optional[pd.DataFrame],
    ) -> ForecastResult:
        """Calculate forecast for a single panel array.

        Args:
            panel: Panel array configuration
            fmi_data: FMI weather data or None for clear sky

        Returns:
            ForecastResult for the array
        """
        today = date.today()
        start_time = datetime(today.year, today.month, today.day)
        end_time = start_time + timedelta(days=3, minutes=-1)

        if fmi_data is not None:
            # Use FMI weather data
            df = fmi_data.copy()
        else:
            # Generate clear sky data
            df = get_clear_sky_irradiance(
                self.latitude,
                self.longitude,
                pd.Timestamp(start_time, tz="UTC"),
                pd.Timestamp(end_time, tz="UTC"),
                timezone="UTC",
            )

        # Process irradiance
        df = transpose_irradiance_to_poa(df, panel, self.latitude, self.longitude)
        df = apply_reflection_losses(df, panel)
        df = estimate_panel_temperature(df, panel)
        df = add_output_to_dataframe(df, panel)

        # Also calculate clear sky for comparison
        clearsky_df = get_clear_sky_irradiance(
            self.latitude,
            self.longitude,
            pd.Timestamp(start_time, tz="UTC"),
            pd.Timestamp(end_time, tz="UTC"),
            timezone="UTC",
        )
        clearsky_df = transpose_irradiance_to_poa(
            clearsky_df, panel, self.latitude, self.longitude
        )
        clearsky_df = apply_reflection_losses(clearsky_df, panel)
        clearsky_df = estimate_panel_temperature(clearsky_df, panel)
        clearsky_df = add_output_to_dataframe(clearsky_df, panel)

        # Build hourly forecast list
        hourly_forecast = []
        for idx, row in df.iterrows():
            time_val = row["time"]
            if hasattr(time_val, "isoformat"):
                dt_str = time_val.isoformat()
            else:
                dt_str = str(time_val)

            # Find matching clear sky value
            clearsky_power = 0.0
            if "time" in clearsky_df.columns:
                mask = clearsky_df["time"] == row["time"]
                if mask.any():
                    clearsky_power = clearsky_df.loc[mask, "output"].iloc[0]

            hourly_forecast.append({
                "datetime": dt_str,
                "power": round(row["output"], 1),
                "power_clear_sky": round(clearsky_power, 1),
            })

        # Calculate daily totals
        daily_energy = calculate_daily_energy(df)
        today_str = str(today)
        tomorrow_str = str(today + timedelta(days=1))

        forecast_today = daily_energy.get(today, 0.0)
        forecast_tomorrow = daily_energy.get(today + timedelta(days=1), 0.0)

        # Find peak power for today
        peak_power, peak_hour = find_peak_power(df, today_str)

        return ForecastResult(
            array=panel,
            hourly_forecast=hourly_forecast,
            forecast_today_kwh=round(forecast_today, 2),
            forecast_tomorrow_kwh=round(forecast_tomorrow, 2),
            peak_power_today=round(peak_power, 1),
            peak_hour_today=peak_hour,
        )

    def should_update(self) -> bool:
        """Check if we should fetch new forecast data."""
        return self.fmi_client.should_update()

    def get_last_update_time(self) -> Optional[datetime]:
        """Get time of last forecast update."""
        return self._last_update
