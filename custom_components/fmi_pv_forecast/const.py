"""Constants for the FMI PV Forecast integration."""
from datetime import timedelta
from typing import Final

DOMAIN: Final = "fmi_pv_forecast"

# Configuration keys
CONF_ARRAYS: Final = "arrays"
CONF_ARRAY_NAME: Final = "name"
CONF_TILT: Final = "tilt"
CONF_AZIMUTH: Final = "azimuth"
CONF_RATED_POWER: Final = "rated_power"
CONF_MODULE_ELEVATION: Final = "module_elevation"
CONF_ALBEDO: Final = "albedo"
CONF_PRODUCTION_SENSOR: Final = "production_sensor"
CONF_UPDATE_INTERVAL: Final = "update_interval"

# Default values
DEFAULT_TILT: Final = 30
DEFAULT_AZIMUTH: Final = 180  # South
DEFAULT_MODULE_ELEVATION: Final = 5
DEFAULT_ALBEDO: Final = 0.25
DEFAULT_UPDATE_INTERVAL: Final = 30  # minutes
DEFAULT_DATA_RESOLUTION: Final = 60  # minutes

# Albedo presets
ALBEDO_PRESETS: Final = {
    "grass": 0.25,
    "concrete": 0.30,
    "snow": 0.80,
    "asphalt": 0.12,
    "soil": 0.17,
    "water": 0.06,
    "custom": None,
}

# Update timing
MIN_UPDATE_INTERVAL: Final = timedelta(minutes=15)
FMI_UPDATE_HOURS: Final = [0, 3, 6, 9, 12, 15, 18, 21]  # UTC hours when FMI updates
FMI_UPDATE_DELAY: Final = timedelta(hours=3)  # Delay after FMI update time

# Forecast data
FORECAST_HOURS: Final = 66  # FMI provides ~66 hours of forecast

# Sensor types
SENSOR_FORECAST_TODAY: Final = "forecast_today"
SENSOR_FORECAST_TOMORROW: Final = "forecast_tomorrow"
SENSOR_POWER_FORECAST: Final = "power_forecast"
SENSOR_PEAK_POWER: Final = "peak_power"
SENSOR_PEAK_HOUR: Final = "peak_hour"
SENSOR_HOURLY_FORECAST: Final = "hourly_forecast"
SENSOR_FORECAST_ACCURACY: Final = "forecast_accuracy"

# Attribution
ATTRIBUTION: Final = "Data provided by FMI Open Data"

# Huld model constants (from original code)
HULD_K1: Final = -0.017162
HULD_K2: Final = -0.040289
HULD_K3: Final = -0.004681
HULD_K4: Final = 0.000148
HULD_K5: Final = 0.000169
HULD_K6: Final = 0.000005
HULD_MIN_EFFICIENCY: Final = 0.5

# Panel temperature model constants (King 2004)
KING_A: Final = -3.56
KING_B: Final = -0.075
KING_DELTA_T: Final = 3
