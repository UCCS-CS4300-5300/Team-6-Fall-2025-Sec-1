"""Database models for itinerary budgeting."""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Budget(models.Model):
    """Container model that groups budget items per user."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]


class BudgetItem(models.Model):
    """Individual budget line items grouped under a budget."""

    TRANSPORTATION = "transportation"
    FOOD_DINING = "food & dining"
    SHOPPING = "shopping"
    EMERGENCY = "emergency"
    OTHER = "other"

    CATEGORY_CHOICES = [
        (TRANSPORTATION, "Transportation"),
        (FOOD_DINING, "Food & Dining"),
        (SHOPPING, "Shopping"),
        (OTHER, "Other"),
    ]

    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="items")
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

    def clean(self):
        """Ensure custom categories are provided only when needed."""
        if self.category == self.OTHER and not self.custom_category.strip():
            raise ValidationError({
                "custom_category": "Please enter a custom category name.",
            })
        if self.category != self.OTHER and self.custom_category.strip():
            raise ValidationError({
                "custom_category": (
                    "Do not set a custom category unless 'Other' is selected."
                ),
            })

    @property
    def effective_category(self) -> str:
        """Return the custom label when 'Other' is chosen."""
        if self.category == self.OTHER:
            return self.custom_category.strip()
        return dict(self.CATEGORY_CHOICES).get(self.category, self.category)
