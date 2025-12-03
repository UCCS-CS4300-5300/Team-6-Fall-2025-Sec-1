"""App configuration for time_preferences."""

from django.apps import AppConfig


class TimePreferencesConfig(AppConfig):
    """Register the time_preferences app with Django."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "time_preferences"
