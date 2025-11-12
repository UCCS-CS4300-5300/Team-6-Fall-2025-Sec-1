from decimal import Decimal

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Itinerary(models.Model):
    """Main itinerary model combining time preferences, budget, and location."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="itineraries")

    # Location information
    location = models.CharField(max_length=200, help_text="Destination location")

    # Time preferences
    wake_up_time = models.TimeField(blank=True, null=True)
    sleep_time = models.TimeField(blank=True, null=True)

    enable_meals = models.BooleanField(default=True)
    breakfast_time = models.TimeField(blank=True, null=True)
    lunch_time = models.TimeField(blank=True, null=True)
    dinner_time = models.TimeField(blank=True, null=True)

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

    break_frequency = models.CharField(max_length=20, choices=BREAK_FREQUENCY_CHOICES, blank=True)
    break_duration = models.CharField(max_length=16, choices=BREAK_DURATION_CHOICES, blank=True)
    schedule_strictness = models.CharField(max_length=16, choices=SCHEDULE_STRICTNESS_CHOICES, blank=True)

    preferred_start_time = models.TimeField(blank=True, null=True)
    preferred_end_time = models.TimeField(blank=True, null=True)

    # Budget information
    total_budget = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        validators=[
            MinValueValidator(0),
            MaxValueValidator(Decimal("1000000000")),
        ],
        help_text="Total budget for the trip"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Itinerary for {self.user} - {self.location} ({self.created_at:%Y-%m-%d})"


class ItineraryBudgetItem(models.Model):
    """Individual budget items for an itinerary."""

    TRANSPORTATION = "transportation"
    FOOD_DINING = "food & dining"
    SHOPPING = "shopping"
    EMERGENCY = "emergency"
    OTHER = "other"

    CATEGORY_CHOICES = [
        (TRANSPORTATION, "Transportation"),
        (FOOD_DINING, "Food & Dining"),
        (SHOPPING, "Shopping"),
        (EMERGENCY, "Emergency"),
        (OTHER, "Other"),
    ]

    itinerary = models.ForeignKey(Itinerary, on_delete=models.CASCADE, related_name="budget_items")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=OTHER)
    custom_category = models.CharField(max_length=120, blank=True)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        validators=[
            MinValueValidator(0),
            MaxValueValidator(Decimal("1000000000")),
        ],
    )

    class Meta:
        ordering = ["id"]

    @property
    def effective_category(self) -> str:
        if self.category == self.OTHER:
            return self.custom_category.strip()
        return dict(self.CATEGORY_CHOICES).get(self.category, self.category)
