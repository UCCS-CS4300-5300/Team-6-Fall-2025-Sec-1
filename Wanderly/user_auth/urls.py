
from django.urls import path, include
from .views import (
    auth_receiver,
    forgot_password_check_email,
    forgot_password_complete,
    forgot_password_request,
    forgot_password_set,
    register,
    reset_password,
    sign_in,
    sign_out,
)

urlpatterns = [
    # Auth urls
    path('sign-in/', sign_in, name='sign_in'),
    path('sign-out/', sign_out, name='sign_out'),
    path('register/', register, name='register'),
    path('forgot-password/', forgot_password_request, name='forgot_password'),
    path('forgot-password/check-email/', forgot_password_check_email,
         name='forgot_password_check_email'),
    path('forgot-password/set/', forgot_password_set, name='forgot_password_set'),
    path('forgot-password/complete/', forgot_password_complete, name='forgot_password_complete'),
    path('auth-receiver/', auth_receiver, name='auth_receiver'),
    path('reset-password/', reset_password, name='reset_password'),
    # urls for the google routing
    path('google_routing/', include('google_routing.urls')),
]
