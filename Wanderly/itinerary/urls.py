"""Urls for important modules"""
from django.urls import path
from .views import itinerary, itinerary_detail, itinerary_list, place_reviews

# pylint: disable=invalid-name
app_name = "itinerary"
urlpatterns = [
    path("", itinerary, name="itinerary"),
    path("list/", itinerary_list, name="itinerary_list"),
    path("<int:itinerary_id>/", itinerary_detail, name="itinerary_detail"),
    path("reviews/", place_reviews, name="place_reviews"),
]
