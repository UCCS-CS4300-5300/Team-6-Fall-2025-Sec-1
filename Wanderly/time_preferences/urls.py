from django.urls import path

from . import views

app_name = "time_preferences"

urlpatterns = [
    path("", views.itinerary, name="itinerary"),
]
