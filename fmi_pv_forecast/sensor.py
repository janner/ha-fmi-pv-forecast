"""Sensor platform for FMI PV Forecast."""
import logging
from datetime import datetime
from typing import Any, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ATTRIBUTION,
    SENSOR_FORECAST_TODAY,
    SENSOR_FORECAST_TOMORROW,
    SENSOR_POWER_FORECAST,
    SENSOR_PEAK_POWER,
    SENSOR_PEAK_HOUR,
    SENSOR_HOURLY_FORECAST,
    SENSOR_FORECAST_ACCURACY,
)
from .coordinator import FMIPVForecastCoordinator
from .forecast import PanelArray, ForecastResult, AggregatedForecast

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FMI PV Forecast sensors from config entry."""
    coordinator: FMIPVForecastCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []

    # Create sensors for each panel array
    for panel in coordinator.panels:
        entities.extend([
            PVForecastTodaySensor(coordinator, panel),
            PVForecastTomorrowSensor(coordinator, panel),
            PVPowerForecastSensor(coordinator, panel),
            PVPeakPowerSensor(coordinator, panel),
            PVPeakHourSensor(coordinator, panel),
            PVHourlyForecastSensor(coordinator, panel),
        ])

    # Create aggregate sensors (total)
    entities.extend([
        PVTotalForecastTodaySensor(coordinator),
        PVTotalForecastTomorrowSensor(coordinator),
        PVTotalPowerForecastSensor(coordinator),
        PVTotalPeakPowerSensor(coordinator),
        PVTotalHourlyForecastSensor(coordinator),
    ])

    # Accuracy sensor (if production sensor configured)
    if coordinator.production_sensor:
        entities.append(PVForecastAccuracySensor(coordinator))

    async_add_entities(entities)


class PVForecastBaseSensor(CoordinatorEntity[FMIPVForecastCoordinator], SensorEntity):
    """Base class for PV forecast sensors."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FMIPVForecastCoordinator,
        panel: Optional[PanelArray] = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._panel = panel

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        if self._panel:
            return DeviceInfo(
                identifiers={(DOMAIN, f"{self.coordinator.entry.entry_id}_{self._panel.id}")},
                name=f"PV Array: {self._panel.name}",
                manufacturer="FMI Open Data",
                model=f"{self._panel.rated_power} kW",
                configuration_url="https://github.com/janner/ha-fmi-pv-forecast",
            )
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name="PV System Total",
            manufacturer="FMI Open Data",
            model="Aggregated",
            configuration_url="https://github.com/janner/ha-fmi-pv-forecast",
        )

    def _get_array_result(self) -> Optional[ForecastResult]:
        """Get forecast result for this panel array."""
        if self.coordinator.data is None or self._panel is None:
            return None
        for result in self.coordinator.data.array_results:
            if result.array.id == self._panel.id:
                return result
        return None


class PVForecastTodaySensor(PVForecastBaseSensor):
    """Sensor for today's forecasted energy (per array)."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator: FMIPVForecastCoordinator, panel: PanelArray) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, panel)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{panel.id}_forecast_today"
        self._attr_name = "Forecast Today"

    @property
    def native_value(self) -> Optional[float]:
        """Return today's forecast."""
        result = self._get_array_result()
        return result.forecast_today_kwh if result else None


class PVForecastTomorrowSensor(PVForecastBaseSensor):
    """Sensor for tomorrow's forecasted energy (per array)."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator: FMIPVForecastCoordinator, panel: PanelArray) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, panel)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{panel.id}_forecast_tomorrow"
        self._attr_name = "Forecast Tomorrow"

    @property
    def native_value(self) -> Optional[float]:
        """Return tomorrow's forecast."""
        result = self._get_array_result()
        return result.forecast_tomorrow_kwh if result else None


class PVPowerForecastSensor(PVForecastBaseSensor):
    """Sensor for current hour's power forecast (per array)."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator: FMIPVForecastCoordinator, panel: PanelArray) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, panel)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{panel.id}_power_forecast"
        self._attr_name = "Power Forecast"

    @property
    def native_value(self) -> Optional[float]:
        """Return current hour's power forecast."""
        result = self._get_array_result()
        if not result or not result.hourly_forecast:
            return None

        now = datetime.now()
        for entry in result.hourly_forecast:
            try:
                dt = datetime.fromisoformat(entry["datetime"].replace("Z", "+00:00"))
                if dt.hour == now.hour and dt.date() == now.date():
                    return entry["power"]
            except (ValueError, KeyError):
                continue
        return None


class PVPeakPowerSensor(PVForecastBaseSensor):
    """Sensor for today's peak power forecast (per array)."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator: FMIPVForecastCoordinator, panel: PanelArray) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, panel)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{panel.id}_peak_power"
        self._attr_name = "Peak Power Today"

    @property
    def native_value(self) -> Optional[float]:
        """Return today's peak power."""
        result = self._get_array_result()
        return result.peak_power_today if result else None


class PVPeakHourSensor(PVForecastBaseSensor):
    """Sensor for today's peak hour (per array)."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: FMIPVForecastCoordinator, panel: PanelArray) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, panel)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{panel.id}_peak_hour"
        self._attr_name = "Peak Hour Today"

    @property
    def native_value(self) -> Optional[datetime]:
        """Return today's peak hour."""
        result = self._get_array_result()
        if not result or not result.peak_hour_today:
            return None
        try:
            return datetime.fromisoformat(result.peak_hour_today.replace("Z", "+00:00"))
        except ValueError:
            return None


class PVHourlyForecastSensor(PVForecastBaseSensor):
    """Sensor containing hourly forecast data (per array)."""

    def __init__(self, coordinator: FMIPVForecastCoordinator, panel: PanelArray) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, panel)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{panel.id}_hourly_forecast"
        self._attr_name = "Hourly Forecast"

    @property
    def native_value(self) -> str:
        """Return OK if forecast available."""
        result = self._get_array_result()
        return "OK" if result and result.hourly_forecast else "unavailable"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return hourly forecast as attributes."""
        result = self._get_array_result()
        if not result:
            return {}

        return {
            "forecast": result.hourly_forecast,
            "last_update": self.coordinator.last_update.isoformat() if self.coordinator.last_update else None,
            "next_update": self.coordinator.get_next_update_time().isoformat() if self.coordinator.get_next_update_time() else None,
        }


# Aggregate (Total) Sensors

class PVTotalForecastTodaySensor(PVForecastBaseSensor):
    """Sensor for today's total forecasted energy."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator: FMIPVForecastCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, None)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_total_forecast_today"
        self._attr_name = "Total Forecast Today"

    @property
    def native_value(self) -> Optional[float]:
        """Return today's total forecast."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.forecast_today_kwh


class PVTotalForecastTomorrowSensor(PVForecastBaseSensor):
    """Sensor for tomorrow's total forecasted energy."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator: FMIPVForecastCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, None)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_total_forecast_tomorrow"
        self._attr_name = "Total Forecast Tomorrow"

    @property
    def native_value(self) -> Optional[float]:
        """Return tomorrow's total forecast."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.forecast_tomorrow_kwh


class PVTotalPowerForecastSensor(PVForecastBaseSensor):
    """Sensor for current hour's total power forecast."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator: FMIPVForecastCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, None)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_total_power_forecast"
        self._attr_name = "Total Power Forecast"

    @property
    def native_value(self) -> Optional[float]:
        """Return current hour's total power forecast."""
        if self.coordinator.data is None or not self.coordinator.data.hourly_forecast:
            return None

        now = datetime.now()
        for entry in self.coordinator.data.hourly_forecast:
            try:
                dt = datetime.fromisoformat(entry["datetime"].replace("Z", "+00:00"))
                if dt.hour == now.hour and dt.date() == now.date():
                    return entry["power"]
            except (ValueError, KeyError):
                continue
        return None


class PVTotalPeakPowerSensor(PVForecastBaseSensor):
    """Sensor for today's total peak power."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator: FMIPVForecastCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, None)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_total_peak_power"
        self._attr_name = "Total Peak Power Today"

    @property
    def native_value(self) -> Optional[float]:
        """Return today's total peak power."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.peak_power_today


class PVTotalHourlyForecastSensor(PVForecastBaseSensor):
    """Sensor containing total hourly forecast data."""

    def __init__(self, coordinator: FMIPVForecastCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, None)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_total_hourly_forecast"
        self._attr_name = "Total Hourly Forecast"

    @property
    def native_value(self) -> str:
        """Return OK if forecast available."""
        if self.coordinator.data is None:
            return "unavailable"
        return "OK" if self.coordinator.data.hourly_forecast else "unavailable"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return hourly forecast as attributes."""
        if self.coordinator.data is None:
            return {}

        return {
            "forecast": self.coordinator.data.hourly_forecast,
            "last_update": self.coordinator.last_update.isoformat() if self.coordinator.last_update else None,
            "next_update": self.coordinator.get_next_update_time().isoformat() if self.coordinator.get_next_update_time() else None,
        }


class PVForecastAccuracySensor(PVForecastBaseSensor):
    """Sensor for forecast accuracy (if production sensor configured)."""

    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: FMIPVForecastCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, None)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_forecast_accuracy"
        self._attr_name = "Forecast Accuracy (7-day)"

    @property
    def native_value(self) -> Optional[float]:
        """Return 7-day forecast accuracy."""
        return self.coordinator.get_accuracy_7day()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional accuracy metrics."""
        return {
            "accuracy_30day": self.coordinator.get_accuracy_30day(),
            "production_sensor": self.coordinator.production_sensor,
        }
