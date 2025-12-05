"""App configuration for the budgets app."""

from django.apps import AppConfig


class BudgetsConfig(AppConfig):
    """Wire up the budgets app for Django."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'budgets'
