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
from .views import index , sign_in, sign_out, auth_receiver, register, forgot_password

urlpatterns = [
    path('', index, name='index'),
    path('admin/', admin.site.urls),

    # Location app urls
    path('location-discovery/', include("location_based_discovery.urls")),

    # Mood app urls
    path('mood/', include("mood.urls", "mood")),

    # Auth urls
    path('sign-in/', sign_in, name='sign_in'),
    path('sign-out/', sign_out, name='sign_out'),
    path('register/', register, name='register'),
    path('forgot-password/', forgot_password, name='forgot_password'),
    path('auth-receiver/', auth_receiver, name='auth_receiver'), 

    # urls for the google routing
    path('google_routing/', include('google_routing.urls')),
]
