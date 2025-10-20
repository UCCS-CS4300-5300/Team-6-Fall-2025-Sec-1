from django.urls import path
from . import views

urlpatterns = [
    # Main page for the in-class demo
    # Will later be used to display map info
    path('', views.route_demo, name='route_demo'),
    
    # API endpoint for computing route
    path("compute/", views.compute_route, name="compute_route"),
]