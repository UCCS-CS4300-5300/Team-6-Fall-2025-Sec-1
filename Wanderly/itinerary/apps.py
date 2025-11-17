"""Apps created by django"""
from django.apps import AppConfig

class ItineraryConfig(AppConfig):
    """Itinerary config controls the django modules and the name of the app"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'itinerary'
