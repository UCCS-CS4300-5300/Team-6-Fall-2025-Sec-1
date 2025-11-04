from django.urls import path

from . import views

app_name = "budgets"

urlpatterns = [
    path("", views.itinerary_budget, name="itinerary_budget"),
]
