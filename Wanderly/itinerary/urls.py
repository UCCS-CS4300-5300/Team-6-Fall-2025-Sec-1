"""Urls for important modules"""
from django.urls import path
from .views import itinerary, itinerary_list

# pylint: disable=invalid-name
app_name = "itinerary"
urlpatterns = [
    path("", itinerary_list, name="itinerary_list"),
    path("itinerary", itinerary, name="itinerary")
]
