from django.urls import path
from .views import mood_questionnaire

app_name = "mood"
urlpatterns = [
    path("", mood_questionnaire, name="questionnaire"),
]