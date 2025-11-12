from django.urls import path

from . import views

app_name = "itinerary"

urlpatterns = [
    path("time-preferences/", views.itinerary_time_preferences, name="time_preferences"),
    path("budget/", views.itinerary_budget, name="budget"),
    path("location/", views.itinerary_location, name="location"),
    path("summary/<int:itinerary_id>/", views.itinerary_summary, name="summary"),
]
