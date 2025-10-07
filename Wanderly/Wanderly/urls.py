from django.urls import path
from .views import index , sign_in, sign_out, auth_receiver


urlpatterns = [
    path('', index, name='index'),

    path('sign-in', sign_in, name='sign_in'),
    path('sign-out', sign_out, name='sign_out'),
    path('auth-receiver', auth_receiver, name='auth_receiver'),
]
 