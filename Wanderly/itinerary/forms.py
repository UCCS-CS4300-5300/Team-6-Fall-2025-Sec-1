"""Controls all of the forms for the itinerary responses"""
from django import forms
from .models import Itinerary, BreakTime, BudgetItem, Day


class ItineraryForm(forms.ModelForm):
    """Form for creating an itinerary"""

    class Meta:
        model = Itinerary
        fields = ['destination', 'place_id', 'latitude', 'longitude',
                  'wake_up_time', 'bed_time', 'num_days']
        widgets = {
            'destination': forms.TextInput(attrs={
                'class': 'form-control js-places',
                'placeholder': 'Enter a city or location...',
                'id': 'id_destination',
            }),
            'place_id': forms.HiddenInput(attrs={'id': 'id_place_id'}),
            'latitude': forms.HiddenInput(attrs={'id': 'id_lat'}),
            'longitude': forms.HiddenInput(attrs={'id': 'id_lng'}),
            'wake_up_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
                'id': 'wake_up_time',
            }),
            'bed_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
                'id': 'bed_time',
            }),
            'num_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'id': 'num_days',
                'min': 1,
                'max': 30,
                'value': 1,
            }),
        }


class BreakTimeForm(forms.ModelForm):
    """Form for break times"""

    class Meta:
        model = BreakTime
        fields = ['start_time', 'end_time']
        widgets = {
            'start_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
                'placeholder': 'Start Time',
            }),
            'end_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
                'placeholder': 'End Time',
            }),
        }


class BudgetItemForm(forms.ModelForm):
    """Form for budget items"""

    class Meta:
        model = BudgetItem
        fields = ['category', 'custom_category', 'amount']
        widgets = {
            'category': forms.Select(attrs={
                'class': 'form-select budget-category-select',
            }),
            'custom_category': forms.TextInput(attrs={
                'class': 'form-control custom-category-input',
                'placeholder': 'Enter category name',
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0',
                'min': 0,
                'step': 0.01,
            }),
        }


class DayForm(forms.ModelForm):
    """Form for individual days"""

    class Meta:
        model = Day
        fields = ['day_number', 'date', 'notes']
        widgets = {
            'day_number': forms.HiddenInput(),
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'E.g., Visit museum, lunch at downtown, etc.',
            }),
        }
