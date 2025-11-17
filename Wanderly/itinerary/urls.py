"""Urls for important modules"""
from django.urls import path
from .views import itinerary, itinerary_detail

app_name = "itinerary"
urlpatterns = [
    path("", itinerary, name="itinerary"),
    path("<int:itinerary_id>/", itinerary_detail, name="itinerary_detail"),
]
