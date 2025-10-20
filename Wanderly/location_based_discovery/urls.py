from django.urls import path
from .views import location_based_discovery, text_search

app_name = "location_based_discovery"
urlpatterns = [
    path("", location_based_discovery, name="location_discovery"),
    path('text_search/', text_search, name='text_search'),
]