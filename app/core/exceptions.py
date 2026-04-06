"""Custom exceptions for Foodie Agent."""


class FoodieAgentError(Exception):
    """Base exception for all Foodie Agent errors."""

    pass


class LocationError(FoodieAgentError):
    """Raised when user location cannot be determined."""

    pass


class PlacesAPIError(FoodieAgentError):
    """Raised when Google Places API fails."""

    pass


class GeocodingAPIError(FoodieAgentError):
    """Raised when Google Geocoding API fails."""

    pass


class GuardrailError(FoodieAgentError):
    """Raised when a guardrail condition is triggered."""

    pass


class AuthenticationError(FoodieAgentError):
    """Raised when JWT authentication fails."""

    pass


class RateLimitError(FoodieAgentError):
    """Raised when rate limit is exceeded."""

    pass
