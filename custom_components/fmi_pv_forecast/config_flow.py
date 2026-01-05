"""Config flow for FMI PV Forecast integration."""
import logging
from typing import Any, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_ARRAYS,
    CONF_ARRAY_NAME,
    CONF_TILT,
    CONF_AZIMUTH,
    CONF_RATED_POWER,
    CONF_MODULE_ELEVATION,
    CONF_ALBEDO,
    CONF_PRODUCTION_SENSOR,
    DEFAULT_TILT,
    DEFAULT_AZIMUTH,
    DEFAULT_MODULE_ELEVATION,
    DEFAULT_ALBEDO,
    ALBEDO_PRESETS,
)

_LOGGER = logging.getLogger(__name__)


class FMIPVForecastConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FMI PV Forecast."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        self._arrays: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step - location setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data[CONF_LATITUDE] = user_input[CONF_LATITUDE]
            self._data[CONF_LONGITUDE] = user_input[CONF_LONGITUDE]
            return await self.async_step_array()

        # Pre-fill with HA's configured location
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LATITUDE,
                        default=self.hass.config.latitude,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=-90,
                            max=90,
                            step=0.000001,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_LONGITUDE,
                        default=self.hass.config.longitude,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=-180,
                            max=180,
                            step=0.000001,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "latitude": str(self.hass.config.latitude),
                "longitude": str(self.hass.config.longitude),
            },
        )

    async def async_step_array(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Handle adding a panel array."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate inputs
            if user_input[CONF_RATED_POWER] <= 0:
                errors[CONF_RATED_POWER] = "invalid_power"
            elif user_input[CONF_TILT] < 0 or user_input[CONF_TILT] > 90:
                errors[CONF_TILT] = "invalid_tilt"
            elif user_input[CONF_AZIMUTH] < 0 or user_input[CONF_AZIMUTH] > 360:
                errors[CONF_AZIMUTH] = "invalid_azimuth"
            else:
                # Get albedo value
                albedo_preset = user_input.get("albedo_preset", "grass")
                if albedo_preset == "custom":
                    albedo = user_input.get(CONF_ALBEDO, DEFAULT_ALBEDO)
                else:
                    albedo = ALBEDO_PRESETS.get(albedo_preset, DEFAULT_ALBEDO)

                # Add the array
                self._arrays.append({
                    CONF_ARRAY_NAME: user_input[CONF_ARRAY_NAME],
                    CONF_TILT: user_input[CONF_TILT],
                    CONF_AZIMUTH: user_input[CONF_AZIMUTH],
                    CONF_RATED_POWER: user_input[CONF_RATED_POWER],
                    CONF_MODULE_ELEVATION: user_input.get(CONF_MODULE_ELEVATION, DEFAULT_MODULE_ELEVATION),
                    CONF_ALBEDO: albedo,
                })

                return await self.async_step_more_arrays()

        # Default name based on number of arrays already added
        default_name = f"Array {len(self._arrays) + 1}"

        return self.async_show_form(
            step_id="array",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ARRAY_NAME, default=default_name): str,
                    vol.Required(CONF_TILT, default=DEFAULT_TILT): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=90,
                            step=1,
                            unit_of_measurement="°",
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Required(CONF_AZIMUTH, default=DEFAULT_AZIMUTH): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=360,
                            step=1,
                            unit_of_measurement="°",
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Required(CONF_RATED_POWER): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.1,
                            max=1000,
                            step=0.1,
                            unit_of_measurement="kW",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_MODULE_ELEVATION, default=DEFAULT_MODULE_ELEVATION
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=100,
                            step=1,
                            unit_of_measurement="m",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional("albedo_preset", default="grass"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": "grass", "label": "Grass (0.25)"},
                                {"value": "concrete", "label": "Concrete (0.30)"},
                                {"value": "snow", "label": "Snow (0.80)"},
                                {"value": "asphalt", "label": "Asphalt (0.12)"},
                                {"value": "soil", "label": "Soil (0.17)"},
                                {"value": "water", "label": "Water (0.06)"},
                                {"value": "custom", "label": "Custom"},
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(CONF_ALBEDO, default=DEFAULT_ALBEDO): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=1,
                            step=0.01,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "array_count": str(len(self._arrays)),
            },
        )

    async def async_step_more_arrays(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Ask if user wants to add more arrays."""
        if user_input is not None:
            if user_input.get("add_more", False):
                return await self.async_step_array()
            return await self.async_step_production_sensor()

        return self.async_show_form(
            step_id="more_arrays",
            data_schema=vol.Schema(
                {
                    vol.Required("add_more", default=False): bool,
                }
            ),
            description_placeholders={
                "array_count": str(len(self._arrays)),
                "array_names": ", ".join(a[CONF_ARRAY_NAME] for a in self._arrays),
            },
        )

    async def async_step_production_sensor(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Configure optional production sensor for accuracy tracking."""
        if user_input is not None:
            production_sensor = user_input.get(CONF_PRODUCTION_SENSOR)
            if production_sensor and production_sensor != "none":
                self._data[CONF_PRODUCTION_SENSOR] = production_sensor

            # Finalize configuration
            self._data[CONF_ARRAYS] = self._arrays

            # Create unique ID based on location
            await self.async_set_unique_id(
                f"{self._data[CONF_LATITUDE]}_{self._data[CONF_LONGITUDE]}"
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"PV Forecast ({len(self._arrays)} arrays)",
                data=self._data,
            )

        # Get all energy sensors for selection
        energy_sensors = []
        for entity_id in self.hass.states.async_entity_ids("sensor"):
            state = self.hass.states.get(entity_id)
            if state and state.attributes.get("device_class") == "energy":
                energy_sensors.append({"value": entity_id, "label": entity_id})

        # Add "none" option
        energy_sensors.insert(0, {"value": "none", "label": "Don't track accuracy"})

        return self.async_show_form(
            step_id="production_sensor",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PRODUCTION_SENSOR, default="none"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=energy_sensors,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            description_placeholders={
                "sensor_count": str(len(energy_sensors) - 1),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return FMIPVForecastOptionsFlow(config_entry)


class FMIPVForecastOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for FMI PV Forecast."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current arrays
        arrays = self.config_entry.data.get(CONF_ARRAYS, [])
        array_names = [a.get(CONF_ARRAY_NAME, f"Array {i+1}") for i, a in enumerate(arrays)]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_PRODUCTION_SENSOR,
                        default=self.config_entry.data.get(CONF_PRODUCTION_SENSOR, ""),
                    ): str,
                }
            ),
            description_placeholders={
                "array_count": str(len(arrays)),
                "array_names": ", ".join(array_names),
            },
        )
