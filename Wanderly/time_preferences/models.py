from django.contrib.auth.models import User
from django.db import models


class TimePreference(models.Model):
    BREAK_FREQUENCY_CHOICES = [
        ("hourly", "Every hour"),
        ("couple_hours", "Every 2-3 hours"),
        ("twice_daily", "Twice per day"),
        ("flexible", "As needed"),
    ]

    BREAK_DURATION_CHOICES = [
        ("quick", "Quick (5-10 min)"),
        ("standard", "Standard (15-20 min)"),
        ("extended", "Extended (30+ min)"),
    ]

    SCHEDULE_STRICTNESS_CHOICES = [
        ("relaxed", "Relaxed"),
        ("moderate", "Moderate"),
        ("precise", "Precise"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="time_preferences")

    wake_up_time = models.TimeField(blank=True, null=True)
    sleep_time = models.TimeField(blank=True, null=True)

    enable_meals = models.BooleanField(default=True)
    breakfast_time = models.TimeField(blank=True, null=True)
    lunch_time = models.TimeField(blank=True, null=True)
    dinner_time = models.TimeField(blank=True, null=True)

    break_frequency = models.CharField(max_length=20, choices=BREAK_FREQUENCY_CHOICES, blank=True)
    break_duration = models.CharField(max_length=16, choices=BREAK_DURATION_CHOICES, blank=True)
    schedule_strictness = models.CharField(max_length=16, choices=SCHEDULE_STRICTNESS_CHOICES, blank=True)

    preferred_start_time = models.TimeField(blank=True, null=True)
    preferred_end_time = models.TimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Time preferences for {self.user} ({self.created_at:%Y-%m-%d})"
