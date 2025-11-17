""" Configuration imports"""
from django.apps import AppConfig

""" Configuration for the user authentication app."""
class UserAuthConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'user_auth'
