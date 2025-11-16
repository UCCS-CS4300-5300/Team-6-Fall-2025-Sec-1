
from django.urls import path, include
from .views import sign_in, sign_out, auth_receiver, register, forgot_password, reset_password

urlpatterns = [
    # Auth urls
    path('sign-in/', sign_in, name='sign_in'),
    path('sign-out/', sign_out, name='sign_out'),
    path('register/', register, name='register'),
    path('forgot-password/', forgot_password, name='forgot_password'),
    path('auth-receiver/', auth_receiver, name='auth_receiver'),
    path('reset-password/', reset_password, name='reset_password'),
    # urls for the google routing
    path('google_routing/', include('google_routing.urls')),
]
