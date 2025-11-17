from django.urls import path, include
from .views import userProfile



urlpatterns = [
    # profile urls
    path('', userProfile, name='user_profile'),
]