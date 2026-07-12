class WeatherError(Exception):
    """Base weather integration error."""


class WeatherConfigurationError(WeatherError):
    """Raised when the weather integration is not configured."""


class WeatherProviderError(WeatherError):
    """Raised when the weather provider request fails."""
