from django.contrib import admin
from .models import MoodResponse

@admin.register(MoodResponse)
class MoodResponseAdmin(admin.ModelAdmin):
    list_display = ['id', 'adventurous', 'energy', 'submitted_at']
    list_filter = ['submitted_at']
    search_fields = ['what_do_you_enjoy']