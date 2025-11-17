'''
Define the necessary urls for home app
'''

from django.contrib import admin
from django.urls import include, path
from home.views import text_search, place_photos

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('Wanderly.urls')),
    path('text_search/', text_search, name='text_search'),
    path('place_photos/<path:photo_name>/', place_photos, name='place_photos'),
]
