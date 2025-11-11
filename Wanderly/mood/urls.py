from django.urls import path
from .views import mood_questionnaire
from home.views import text_search

app_name = "mood"
urlpatterns = [
    path("", mood_questionnaire, name="mood_questionnaire"),
    path('text_search/', text_search, name='text_search'),
]