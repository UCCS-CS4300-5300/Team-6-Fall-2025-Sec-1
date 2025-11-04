from django import forms
from django.forms import formset_factory

from .models import BudgetItem


class BudgetItemForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        category_field = self.fields["category"]
        category_choices = list(category_field.choices)
        if category_choices:
            if category_choices[0][0] == "":
                category_choices[0] = ("", "Select a category")
            else:
                category_choices.insert(0, ("", "Select a category"))
        else:
            category_choices = [("", "Select a category")]
        category_field.choices = category_choices

    class Meta:
        model = BudgetItem
        fields = ("category", "custom_category", "amount")
        widgets = {
            "category": forms.Select(attrs={"class": "form-select budget-category"}),
            "custom_category": forms.TextInput(
                attrs={
                    "class": "form-control custom-category",
                    "placeholder": "Enter category name",
                }
            ),
            "amount": forms.NumberInput(
                attrs={
                    "class": "form-control budget-amount",
                    "min": 0,
                    "step": "1",
                    "placeholder": "Amount",
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get("category")
        custom_category = cleaned_data.get("custom_category", "").strip()
        amount = cleaned_data.get("amount")

        if category == BudgetItem.OTHER and not custom_category:
            self.add_error("custom_category", "Please enter a custom category name.")
        if category != BudgetItem.OTHER:
            cleaned_data["custom_category"] = ""

        if amount is None:
            self.add_error("amount", "Enter a budget amount.")

        return cleaned_data

    def save(self, budget, commit=True):
        item = super().save(commit=False)
        item.budget = budget
        if commit:
            item.save()
        return item


BudgetItemFormSet = formset_factory(BudgetItemForm, extra=1, can_delete=False)
