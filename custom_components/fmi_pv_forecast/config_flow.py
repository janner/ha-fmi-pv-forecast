"""Config flow for FMI PV Forecast integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import callback

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


class FMIPVForecastConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FMI PV Forecast."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        self._arrays: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - location setup."""
        if user_input is not None:
            self._data[CONF_LATITUDE] = user_input[CONF_LATITUDE]
            self._data[CONF_LONGITUDE] = user_input[CONF_LONGITUDE]
            return await self.async_step_array()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LATITUDE,
                        default=self.hass.config.latitude,
                    ): vol.Coerce(float),
                    vol.Required(
                        CONF_LONGITUDE,
                        default=self.hass.config.longitude,
                    ): vol.Coerce(float),
                }
            ),
        )

    async def async_step_array(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle adding a panel array."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Basic validation
            if user_input[CONF_RATED_POWER] <= 0:
                errors[CONF_RATED_POWER] = "invalid_power"
            
            if not errors:
                # Get albedo value from preset
                albedo_preset = user_input.get("albedo_preset", "grass")
                if albedo_preset == "custom":
                    albedo = user_input.get(CONF_ALBEDO, DEFAULT_ALBEDO)
                else:
                    albedo = ALBEDO_PRESETS.get(albedo_preset, DEFAULT_ALBEDO)

                self._arrays.append({
                    CONF_ARRAY_NAME: user_input[CONF_ARRAY_NAME],
                    CONF_TILT: user_input[CONF_TILT],
                    CONF_AZIMUTH: user_input[CONF_AZIMUTH],
                    CONF_RATED_POWER: user_input[CONF_RATED_POWER],
                    CONF_MODULE_ELEVATION: user_input.get(CONF_MODULE_ELEVATION, DEFAULT_MODULE_ELEVATION),
                    CONF_ALBEDO: albedo,
                })
                return await self.async_step_more_arrays()

        default_name = f"Array {len(self._arrays) + 1}"

        return self.async_show_form(
            step_id="array",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ARRAY_NAME, default=default_name): str,
                    vol.Required(CONF_TILT, default=DEFAULT_TILT): vol.Coerce(float),
                    vol.Required(CONF_AZIMUTH, default=DEFAULT_AZIMUTH): vol.Coerce(float),
                    vol.Required(CONF_RATED_POWER): vol.Coerce(float),
                    vol.Optional(CONF_MODULE_ELEVATION, default=DEFAULT_MODULE_ELEVATION): vol.Coerce(float),
                    vol.Optional("albedo_preset", default="grass"): vol.In(
                        ["grass", "concrete", "snow", "asphalt", "soil", "water", "custom"]
                    ),
                    vol.Optional(CONF_ALBEDO, default=DEFAULT_ALBEDO): vol.Coerce(float),
                }
            ),
            errors=errors,
        )

    async def async_step_more_arrays(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask if user wants to add more arrays."""
        if user_input is not None:
            if user_input.get("add_more", False):
                return await self.async_step_array()
            
            # Finalize
            self._data[CONF_ARRAYS] = self._arrays
            
            await self.async_set_unique_id(
                f"{self._data[CONF_LATITUDE]}_{self._data[CONF_LONGITUDE]}"
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"PV Forecast ({len(self._arrays)} arrays)",
                data=self._data,
            )

        return self.async_show_form(
            step_id="more_arrays",
            data_schema=vol.Schema(
                {
                    vol.Required("add_more", default=False): bool,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return FMIPVForecastOptionsFlow(config_entry)


class FMIPVForecastOptionsFlow(OptionsFlow):
    """Handle options flow for FMI PV Forecast."""

    def __init__(self, config_entry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_PRODUCTION_SENSOR,
                        default=self.config_entry.options.get(CONF_PRODUCTION_SENSOR, ""),
                    ): str,
                }
            ),
        )
