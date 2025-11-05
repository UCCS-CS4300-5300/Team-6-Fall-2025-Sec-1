from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Budget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]


class BudgetItem(models.Model):
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
        if self.category == self.OTHER and not self.custom_category.strip():
            raise ValidationError({"custom_category": "Please enter a custom category name."})
        if self.category != self.OTHER and self.custom_category.strip():
            raise ValidationError({"custom_category": "Do not set a custom category unless 'Other' is selected."})

    @property
    def effective_category(self) -> str:
        if self.category == self.OTHER:
            return self.custom_category.strip()
        return dict(self.CATEGORY_CHOICES).get(self.category, self.category)
