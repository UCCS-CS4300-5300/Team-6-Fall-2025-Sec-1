from django.contrib import admin
from django.urls import path
from .views import index , sign_in, sign_out, auth_receiver, register, forgot_password


urlpatterns = [
    path('', index, name='index'),
    path('admin/', admin.site.urls),

    path('sign-in/', sign_in, name='sign_in'),
    path('sign-out/', sign_out, name='sign_out'),
    path('register/', register, name='register'),
    path('forgot-password/', forgot_password, name='forgot_password'),

    path('auth-receiver/', auth_receiver, name='auth_receiver'), 

]
 
