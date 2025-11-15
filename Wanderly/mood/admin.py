'''
Admin View of Mood Based Discovery
'''

from django.contrib import admin
from .models import MoodResponse

@admin.register(MoodResponse)
class MoodResponseAdmin(admin.ModelAdmin):
    ''' Defines how the mood should be displayed to admins'''
    list_display = ['id', 'adventurous', 'energy', 'submitted_at']
    list_filter = ['submitted_at']
    search_fields = ['what_do_you_enjoy']
