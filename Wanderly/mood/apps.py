'''
Define the app configuration for the mood app
'''
from django.apps import AppConfig

class MoodConfig(AppConfig):
    ''' Define the app configuration on start up '''
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mood'
