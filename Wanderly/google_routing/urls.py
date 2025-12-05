"""
These urls connect the route demo page to the main page,
and the compute_route is the API endpoint for getting
the map information.
"""
from django.urls import path
from . import views

app_name = "google_routing"

urlpatterns = [
    # Main page for the in-class demo
    # Will later be used to display map info
    path('', views.route_demo, name='route_demo'),

    # API endpoint for computing route
    path("compute/", views.compute_route, name="compute_route"),
]
