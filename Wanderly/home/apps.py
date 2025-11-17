'''
Define the app configuration for the home app
'''
from django.apps import AppConfig

class HomeConfig(AppConfig):
    ''' Define the app configuration on start up '''
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'home'
