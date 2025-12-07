"""controls the urls for the mood app"""
from django.urls import path
from home.views import text_search
from .views import mood_questionnaire

app_name = "mood"
urlpatterns = [
    path("", mood_questionnaire, name="mood_questionnaire"),
    path('text_search/', text_search, name='text_search'),
]
