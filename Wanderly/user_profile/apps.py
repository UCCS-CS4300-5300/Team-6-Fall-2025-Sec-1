"""Configuration for the user_profile app."""
from django.apps import AppConfig


class UserProfileConfig(AppConfig):
    """ App configuration for user profiles. """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'user_profile'
