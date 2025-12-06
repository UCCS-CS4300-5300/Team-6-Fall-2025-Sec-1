""" Configuration imports"""
from django.apps import AppConfig

"""Configuration for the user authentication app."""


class UserAuthConfig(AppConfig):
    """Application configuration for the user_auth app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'user_auth'
