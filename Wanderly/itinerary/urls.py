from django.urls import path
from .views import itinerary
from home.views import text_search

app_name = "itinerary"
urlpatterns = [
    path("", itinerary, name="itinerary"),
]