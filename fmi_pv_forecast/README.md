# FMI PV Forecast for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Home Assistant integration that provides solar PV generation forecasts using **FMI Open Data** weather forecasts from the Finnish Meteorological Institute.

## Features

- 🌤️ **Weather-based forecasts** using FMI Open Data (MetCoOp numerical weather prediction)
- ☀️ **Clear sky comparison** showing theoretical maximum generation
- 📊 **Multiple panel arrays** support with different orientations
- 📈 **Hourly forecast data** for up to 66 hours ahead
- 🔌 **Energy Dashboard** compatible sensors
- 📉 **Accuracy tracking** by comparing forecasts with actual production
- 🎨 **ApexCharts** card examples for interactive visualization

## Attribution

This integration is based on the excellent work from the **Finnish Meteorological Institute (FMI)**:

> **Original Project:** [fmidev/fmi-open-pv-forecast](https://github.com/fmidev/fmi-open-pv-forecast)
>
> **Original Authors:** Timo Salola, Viivi Kallio
>
> **License:** MIT License
>
> The forecast engine uses models and research by the international scientific community:
> - PV estimation model as described by Huld et al. (2010)
> - PV related tools from the [PVlib Python package](https://pvlib-python.readthedocs.io/)
> - FMI Open Data weather forecasts

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add `https://github.com/janner/ha-fmi-pv-forecast` as an Integration
6. Click "Install"
7. Restart Home Assistant

### Manual Installation

1. Download the `custom_components/fmi_pv_forecast` folder
2. Copy it to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "FMI PV Forecast"
4. Follow the configuration wizard:
   - **Step 1:** Confirm your location (pre-filled from HA config)
   - **Step 2:** Add your first panel array (name, tilt, azimuth, power)
   - **Step 3:** Add more arrays if needed
   - **Step 4:** Optionally select a production sensor for accuracy tracking

### Panel Array Configuration

| Parameter | Description | Example |
|-----------|-------------|---------|
| Name | Descriptive name for the array | "South Roof" |
| Tilt | Panel tilt angle (0° = horizontal, 90° = vertical) | 30° |
| Azimuth | Panel direction (0° = North, 180° = South) | 180° |
| Rated Power | System capacity in kW | 10.0 kW |
| Module Elevation | Height above ground (for temperature modeling) | 5 m |
| Ground Surface | Affects ground reflection (grass, snow, etc.) | Grass |

## Sensors

### Per Panel Array

| Sensor | Description |
|--------|-------------|
| `sensor.pv_array_X_forecast_today` | Forecasted energy for today (kWh) |
| `sensor.pv_array_X_forecast_tomorrow` | Forecasted energy for tomorrow (kWh) |
| `sensor.pv_array_X_power_forecast` | Current hour's power forecast (W) |
| `sensor.pv_array_X_peak_power` | Today's peak power forecast (W) |
| `sensor.pv_array_X_peak_hour` | Time of peak production |
| `sensor.pv_array_X_hourly_forecast` | Full hourly forecast data |

### Aggregate (Total)

| Sensor | Description |
|--------|-------------|
| `sensor.pv_total_forecast_today` | Combined total for all arrays |
| `sensor.pv_total_forecast_tomorrow` | Combined tomorrow's forecast |
| `sensor.pv_total_power_forecast` | Combined current power |
| `sensor.pv_total_peak_power` | Combined peak power |
| `sensor.pv_total_hourly_forecast` | Combined hourly data |

### Hourly Forecast Data Structure

The `hourly_forecast` sensor contains forecast data in its attributes:

```yaml
state: "OK"
attributes:
  forecast:
    - datetime: "2026-01-05T06:00:00+00:00"
      power: 0
      power_clear_sky: 0
    - datetime: "2026-01-05T07:00:00+00:00"
      power: 245
      power_clear_sky: 890
    # ... up to 66 hours
  last_update: "2026-01-05T03:15:00+00:00"
  next_update: "2026-01-05T06:15:00+00:00"
```

## Visualization

### ApexCharts Card

Install [apexcharts-card](https://github.com/RomRider/apexcharts-card) from HACS and use this configuration:

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Solar PV Forecast
graph_span: 3d
span:
  start: day
series:
  - entity: sensor.pv_system_total_total_hourly_forecast
    name: Forecast
    type: area
    color: "#303193"
    data_generator: |
      return entity.attributes.forecast.map((entry) => {
        return [new Date(entry.datetime).getTime(), entry.power];
      });
  - entity: sensor.pv_system_total_total_hourly_forecast
    name: Clear Sky
    type: line
    color: "#6ec8fa"
    data_generator: |
      return entity.attributes.forecast.map((entry) => {
        return [new Date(entry.datetime).getTime(), entry.power_clear_sky];
      });
```

More examples are available in the [examples folder](examples/apexcharts_card.yaml).

### Energy Dashboard

The `forecast_today` sensors are compatible with Home Assistant's Energy Dashboard as solar forecast sources.

## Update Schedule

The integration syncs with FMI's data update schedule:
- FMI updates forecasts every 3 hours (00, 03, 06, 09, 12, 15, 18, 21 UTC)
- Data becomes available approximately 3 hours after the model run
- The integration checks for new data every 30 minutes

## Geographic Coverage

This integration works for locations covered by FMI Open Data, which includes:
- Finland
- Scandinavia
- Baltic region
- Parts of Northern Europe

See [FMI Numerical Weather Prediction coverage](https://en.ilmatieteenlaitos.fi/numerical-weather-prediction) for details.

## Troubleshooting

### Forecast higher than actual production
- Check panel angles and rated power configuration
- Panels may have degraded over time
- Shading from trees or buildings not accounted for

### Forecast lower than actual production
- Cloud edge reflections can temporarily boost production
- Configuration may underestimate system capacity

### No data available
- Check if your location is within FMI coverage area
- FMI Open Data may be temporarily unavailable

## References

- [FMI Open Data](https://en.ilmatieteenlaitos.fi/open-data)
- [PVlib Python](https://pvlib-python.readthedocs.io/)
- [Huld PV Model (2010)](https://doi.org/10.1016/j.solener.2009.10.022)
- [Original fmi-open-pv-forecast](https://github.com/fmidev/fmi-open-pv-forecast)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright 2024-2026 Finnish Meteorological Institute (original code)
Copyright 2026 @janner (Home Assistant integration)
