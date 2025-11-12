from django import forms
from django.forms import formset_factory

from .models import Itinerary, ItineraryBudgetItem


class ItineraryTimePreferenceForm(forms.ModelForm):
    """Form for time preference section of itinerary."""

    enable_meals = forms.BooleanField(
        required=False,
        label="Include meal times",
        initial=True,
    )

    class Meta:
        model = Itinerary
        fields = [
            "wake_up_time",
            "sleep_time",
            "enable_meals",
            "breakfast_time",
            "lunch_time",
            "dinner_time",
            "break_frequency",
            "break_duration",
            "schedule_strictness",
            "preferred_start_time",
            "preferred_end_time",
        ]
        widgets = {
            "wake_up_time": forms.TimeInput(attrs={"type": "time", "class": "form-control form-control-lg"}),
            "sleep_time": forms.TimeInput(attrs={"type": "time", "class": "form-control form-control-lg"}),
            "breakfast_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "lunch_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "dinner_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "break_frequency": forms.Select(attrs={"class": "form-select"}),
            "break_duration": forms.Select(attrs={"class": "form-select"}),
            "schedule_strictness": forms.Select(attrs={"class": "form-select"}),
            "preferred_start_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "preferred_end_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Mark time fields as optional
        for field_name in ("wake_up_time", "sleep_time", "breakfast_time", "lunch_time", "dinner_time",
                           "preferred_start_time", "preferred_end_time"):
            self.fields[field_name].required = False

        # Mark choice fields as optional and update placeholder
        for choice_field in ("break_frequency", "break_duration", "schedule_strictness"):
            field = self.fields[choice_field]
            field.required = False
            choices = list(field.choices)
            if choices and choices[0][0] == "":
                choices[0] = ("", "---------")
            field.choices = choices
            field.widget.choices = choices

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("enable_meals"):
            cleaned["breakfast_time"] = None
            cleaned["lunch_time"] = None
            cleaned["dinner_time"] = None

        start = cleaned.get("preferred_start_time")
        end = cleaned.get("preferred_end_time")
        if start and end and start >= end:
            self.add_error("preferred_end_time", "End time must be after start time.")

        return cleaned


class ItineraryBudgetForm(forms.ModelForm):
    """Form for budget section of itinerary."""

    class Meta:
        model = Itinerary
        fields = ["total_budget"]
        widgets = {
            "total_budget": forms.NumberInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "min": 0,
                    "step": "0.01",
                    "placeholder": "Enter total budget",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["total_budget"].required = True


class ItineraryBudgetItemForm(forms.ModelForm):
    """Form for individual budget items."""

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
        model = ItineraryBudgetItem
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

        if category == ItineraryBudgetItem.OTHER and not custom_category:
            self.add_error("custom_category", "Please enter a custom category name.")
        if category != ItineraryBudgetItem.OTHER:
            cleaned_data["custom_category"] = ""

        if amount is None:
            self.add_error("amount", "Enter a budget amount.")

        return cleaned_data


ItineraryBudgetItemFormSet = formset_factory(ItineraryBudgetItemForm, extra=1, can_delete=False)


class ItineraryLocationForm(forms.ModelForm):
    """Form for location section of itinerary."""

    class Meta:
        model = Itinerary
        fields = ["location"]
        widgets = {
            "location": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg js-places",
                    "placeholder": "Enter a city or location...",
                    "data-places": "1",
                    "data-types": "geocode",
                    "data-country": "us"
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["location"].required = True
