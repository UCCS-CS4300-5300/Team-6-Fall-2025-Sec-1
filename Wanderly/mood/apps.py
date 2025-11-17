"""creates django app named mood"""
from django.apps import AppConfig


class MoodConfig(AppConfig):
    """mood configuration class created by django"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mood'
