"""
URL configuration for Wanderly project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from Wanderly.views import index
from home.views import text_search, place_photos

urlpatterns = [
    path('', index, name='index'),
    path('admin/', admin.site.urls),

    # Home New Google Places API urls
    path('text_search/', text_search, name='text_search'),
    path('place_photos/<path:photo_name>/', place_photos, name='place_photos'),

    # Mood app urls
    path('mood/', include("mood.urls", "mood")),

    # Auth urls
    path('auth/', include('user_auth.urls')),

    # urls for the google routing
    path('google_routing/', include('google_routing.urls')),


    # urls for Budget planner
    path('budget/', include('budgets.urls', 'budgets')),

    # Time preferences planner
    path('time-preferences/', include('time_preferences.urls')),

    # Itinerary planner (combines time preferences, budget, and location)
    path('itinerary/', include('itinerary.urls')),

    # User profile urls
    path('profile/', include('user_profile.urls')),

    # Itinerary list view
    path('itinerary_list/', include('itinerary.urls')),
]
