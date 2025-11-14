"""Urls for important modules"""
from django.urls import path
from .views import itinerary

app_name = "itinerary"
urlpatterns = [
    path("", itinerary, name="itinerary"),
]
