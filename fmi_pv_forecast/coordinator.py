"""Data update coordinator for FMI PV Forecast."""
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    CONF_ARRAYS,
    CONF_PRODUCTION_SENSOR,
    DEFAULT_UPDATE_INTERVAL,
)
from .forecast import ForecastEngine, PanelArray, AggregatedForecast

_LOGGER = logging.getLogger(__name__)


class FMIPVForecastCoordinator(DataUpdateCoordinator[AggregatedForecast]):
    """Coordinator for fetching and updating PV forecast data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            entry: Config entry
        """
        self.entry = entry
        self.latitude = entry.data.get(CONF_LATITUDE, hass.config.latitude)
        self.longitude = entry.data.get(CONF_LONGITUDE, hass.config.longitude)
        self.timezone = str(hass.config.time_zone)
        self.production_sensor = entry.data.get(CONF_PRODUCTION_SENSOR)

        # Initialize panel arrays
        self.panels: list[PanelArray] = []
        for array_data in entry.data.get(CONF_ARRAYS, []):
            self.panels.append(PanelArray.from_dict(array_data))

        # Initialize forecast engine
        self.engine = ForecastEngine(
            latitude=self.latitude,
            longitude=self.longitude,
            timezone=self.timezone,
        )

        # Historical accuracy tracking
        self._forecast_history: list[dict] = []
        self._accuracy_7day: Optional[float] = None
        self._accuracy_30day: Optional[float] = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> AggregatedForecast:
        """Fetch data from FMI and calculate forecast.

        Returns:
            AggregatedForecast with all array data
        """
        try:
            # Run forecast calculation in executor
            forecast = await self.hass.async_add_executor_job(
                self.engine.calculate_forecast,
                self.panels,
                True,  # use_fmi
            )

            # Update accuracy tracking if we have a production sensor
            if self.production_sensor:
                await self._update_accuracy_tracking()

            return forecast

        except Exception as err:
            _LOGGER.error("Error fetching PV forecast: %s", err)
            raise UpdateFailed(f"Error fetching PV forecast: {err}") from err

    async def _update_accuracy_tracking(self) -> None:
        """Update forecast accuracy tracking.

        Compares previous day's forecast with actual production.
        """
        if not self.production_sensor:
            return

        try:
            # Get actual production from sensor
            state = self.hass.states.get(self.production_sensor)
            if state is None or state.state in ("unknown", "unavailable"):
                return

            # This is a simplified implementation
            # A full implementation would track historical forecasts and compare
            # with actual production over time using the recorder

            _LOGGER.debug(
                "Production sensor %s state: %s",
                self.production_sensor,
                state.state,
            )

        except Exception as err:
            _LOGGER.warning("Error updating accuracy tracking: %s", err)

    def get_accuracy_7day(self) -> Optional[float]:
        """Get 7-day rolling forecast accuracy."""
        return self._accuracy_7day

    def get_accuracy_30day(self) -> Optional[float]:
        """Get 30-day rolling forecast accuracy."""
        return self._accuracy_30day

    @property
    def last_update(self) -> Optional[datetime]:
        """Get last update time."""
        return self.engine.get_last_update_time()

    def get_next_update_time(self) -> Optional[datetime]:
        """Calculate next expected update time based on FMI schedule."""
        if self.last_update is None:
            return None

        now = datetime.utcnow()
        fmi_update_hours = [0, 3, 6, 9, 12, 15, 18, 21]
        delay_hours = 3

        for hour in fmi_update_hours:
            update_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            available_time = update_time + timedelta(hours=delay_hours)

            if available_time > now:
                return available_time

        # Next day's first update
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=delay_hours, minute=0, second=0, microsecond=0)
