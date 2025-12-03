"""Urls for important modules"""
from django.urls import path
from .views import itinerary, itinerary_detail, itinerary_list, place_reviews, find_itinerary

# pylint: disable=invalid-name
app_name = "itinerary"
urlpatterns = [
    path("", itinerary, name="itinerary"),
    path("list/", itinerary_list, name="itinerary_list"),
    path("<int:itinerary_id>/", itinerary_detail, name="itinerary_detail"),
    path("reviews/", place_reviews, name="place_reviews"),
    path("access/", find_itinerary, name="find_itinerary"), # Where the find_itinerary runs
    path("<str:access_code>/", itinerary_detail, name="itinerary_detail"),
]
