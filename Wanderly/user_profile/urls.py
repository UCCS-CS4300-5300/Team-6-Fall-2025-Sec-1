""" URL configurations for user profile app """

from django.urls import path
from .views import user_profile

urlpatterns = [
    # profile urls
    path('', user_profile, name='user_profile'),
]
