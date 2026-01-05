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

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL as an Integration
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
4. Follow the configuration wizard

## Attribution

Based on [fmidev/fmi-open-pv-forecast](https://github.com/fmidev/fmi-open-pv-forecast) by the Finnish Meteorological Institute.

**Original Authors:** Timo Salola, Viivi Kallio

See the full [README](custom_components/fmi_pv_forecast/README.md) for detailed documentation.
