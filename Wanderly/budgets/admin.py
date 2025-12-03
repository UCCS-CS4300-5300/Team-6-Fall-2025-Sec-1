"""Admin registrations for the budgets app."""

from django.contrib import admin

from .models import Budget, BudgetItem


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    """List configuration for the Budget model."""

    list_display = ("id", "user", "created_at")
    search_fields = ("user__username", "user__email")
    list_filter = ("created_at",)


@admin.register(BudgetItem)
class BudgetItemAdmin(admin.ModelAdmin):
    """List configuration for individual budget items."""

    list_display = ("id", "budget", "category", "custom_category", "amount")
    list_filter = ("category",)
    search_fields = ("custom_category", "budget__user__username", "budget__user__email")
