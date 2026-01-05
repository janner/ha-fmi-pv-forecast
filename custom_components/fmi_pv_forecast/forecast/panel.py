"""Panel array configuration dataclass."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PanelArray:
    """Represents a solar panel array configuration."""

    name: str
    tilt: float  # degrees, 0 = horizontal, 90 = vertical
    azimuth: float  # degrees, 0 = north, 90 = east, 180 = south, 270 = west
    rated_power: float  # kW
    module_elevation: float = 5.0  # meters above ground
    albedo: float = 0.25  # ground reflectivity

    # Computed/cached values
    id: str = field(default="", init=False)

    def __post_init__(self):
        """Generate ID from name."""
        self.id = self.name.lower().replace(" ", "_").replace("-", "_")

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "name": self.name,
            "tilt": self.tilt,
            "azimuth": self.azimuth,
            "rated_power": self.rated_power,
            "module_elevation": self.module_elevation,
            "albedo": self.albedo,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PanelArray":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            tilt=data["tilt"],
            azimuth=data["azimuth"],
            rated_power=data["rated_power"],
            module_elevation=data.get("module_elevation", 5.0),
            albedo=data.get("albedo", 0.25),
        )


@dataclass
class ForecastResult:
    """Result of a forecast calculation for a single array."""

    array: PanelArray
    hourly_forecast: list[dict]  # List of {datetime, power, power_clear_sky}
    forecast_today_kwh: float
    forecast_tomorrow_kwh: float
    peak_power_today: float
    peak_hour_today: Optional[str]  # ISO format datetime string

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "array_name": self.array.name,
            "array_id": self.array.id,
            "hourly_forecast": self.hourly_forecast,
            "forecast_today_kwh": self.forecast_today_kwh,
            "forecast_tomorrow_kwh": self.forecast_tomorrow_kwh,
            "peak_power_today": self.peak_power_today,
            "peak_hour_today": self.peak_hour_today,
        }


@dataclass
class AggregatedForecast:
    """Aggregated forecast for all arrays combined."""

    hourly_forecast: list[dict]
    forecast_today_kwh: float
    forecast_tomorrow_kwh: float
    peak_power_today: float
    peak_hour_today: Optional[str]
    array_results: list[ForecastResult] = field(default_factory=list)

    @classmethod
    def from_results(cls, results: list[ForecastResult]) -> "AggregatedForecast":
        """Create aggregated forecast from individual array results."""
        if not results:
            return cls(
                hourly_forecast=[],
                forecast_today_kwh=0.0,
                forecast_tomorrow_kwh=0.0,
                peak_power_today=0.0,
                peak_hour_today=None,
                array_results=[],
            )

        # Aggregate hourly forecasts
        hourly_by_time: dict[str, dict] = {}
        for result in results:
            for entry in result.hourly_forecast:
                dt = entry["datetime"]
                if dt not in hourly_by_time:
                    hourly_by_time[dt] = {
                        "datetime": dt,
                        "power": 0.0,
                        "power_clear_sky": 0.0,
                    }
                hourly_by_time[dt]["power"] += entry["power"]
                hourly_by_time[dt]["power_clear_sky"] += entry["power_clear_sky"]

        hourly_forecast = sorted(hourly_by_time.values(), key=lambda x: x["datetime"])

        # Sum totals
        forecast_today_kwh = sum(r.forecast_today_kwh for r in results)
        forecast_tomorrow_kwh = sum(r.forecast_tomorrow_kwh for r in results)

        # Find peak
        peak_power_today = 0.0
        peak_hour_today = None
        for entry in hourly_forecast:
            if entry["power"] > peak_power_today:
                peak_power_today = entry["power"]
                peak_hour_today = entry["datetime"]

        return cls(
            hourly_forecast=hourly_forecast,
            forecast_today_kwh=forecast_today_kwh,
            forecast_tomorrow_kwh=forecast_tomorrow_kwh,
            peak_power_today=peak_power_today,
            peak_hour_today=peak_hour_today,
            array_results=results,
        )
