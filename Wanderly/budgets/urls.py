"""URL patterns for the budgets app."""

from django.urls import path

from .views import itinerary_budget

app_name = "budgets"

urlpatterns = [
    path("", itinerary_budget, name="itinerary_budget"),
]
