"""
Application configuration for the places_auto_complete app.
Defines the Django AppConfig used to register the app and configure its
default settings.
"""
from django.apps import AppConfig

class PlacesAutoCompleteConfig(AppConfig):
    """App configuration class for the places_auto_complete Django application."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'places_auto_complete'
