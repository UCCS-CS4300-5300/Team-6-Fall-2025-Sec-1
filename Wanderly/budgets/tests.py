from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from .forms import BudgetItemForm
from .models import Budget, BudgetItem


class BudgetModelTests(TestCase):
    def test_budget_creation(self):
        user = get_user_model().objects.create_user(
            username="creator",
            email="creator@example.com",
            password="pass1234",
        )
        budget = Budget.objects.create(user=user)

        self.assertEqual(Budget.objects.count(), 1)
        stored = Budget.objects.get(pk=budget.pk)
        self.assertEqual(stored.user, user)
        self.assertIsNotNone(stored.created_at)


class BudgetItemFormTests(TestCase):
    def test_budget_item_form_validation(self):
        # Missing custom category when "Other" is selected → invalid
        missing_custom = BudgetItemForm(
            data={
                "category": BudgetItem.OTHER,
                "custom_category": "",
                "amount": "100",
            }
        )
        self.assertFalse(missing_custom.is_valid())
        self.assertIn("custom_category", missing_custom.errors)

        # Providing custom category with "Other" passes validation
        valid_form = BudgetItemForm(
            data={
                "category": BudgetItem.OTHER,
                "custom_category": "Souvenirs",
                "amount": "150.50",
            }
        )
        self.assertTrue(valid_form.is_valid())
        self.assertEqual(valid_form.cleaned_data["custom_category"], "Souvenirs")

        # Non-"Other" categories should clear custom category and validate
        regular_form = BudgetItemForm(
            data={
                "category": BudgetItem.TRANSPORTATION,
                "custom_category": "Should be ignored",
                "amount": Decimal("75.00"),
            }
        )
        self.assertTrue(regular_form.is_valid())
        self.assertEqual(regular_form.cleaned_data["custom_category"], "")
