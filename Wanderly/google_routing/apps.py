"""
Application configuration for the google_routing app.
Defines the Django AppConfig used to register the app and configure its
default settings.
"""
from django.apps import AppConfig

class GoogleRoutingConfig(AppConfig):
    """App configuration class for the google_routing Django application."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'google_routing'
