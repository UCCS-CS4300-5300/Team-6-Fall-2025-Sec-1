"""Admin configuration for time preference entries."""

from django.contrib import admin

from .models import TimePreference


@admin.register(TimePreference)
class TimePreferenceAdmin(admin.ModelAdmin):
    """Display useful fields in the Django admin list view."""

    list_display = ("id", "user", "wake_up_time", "sleep_time", "created_at")
    search_fields = ("user__username", "user__email")
    list_filter = ("break_frequency", "schedule_strictness", "created_at")
