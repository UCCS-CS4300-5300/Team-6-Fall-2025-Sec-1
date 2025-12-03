"""URL patterns for the time_preferences app."""

from django.urls import path

from .views import itinerary

app_name = "time_preferences"

urlpatterns = [
    path("", itinerary, name="itinerary"),
]
