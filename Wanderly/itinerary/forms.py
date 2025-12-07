"""Controls all of the forms for the itinerary responses"""
from django import forms
from .models import Itinerary, BreakTime, BudgetItem, Day


class ItineraryForm(forms.ModelForm):
    """Form for creating an itinerary"""

    class Meta:
        """Meta class for ItineraryForm"""
        model = Itinerary
        fields = [
            'destination',
            'place_id',
            'latitude',
            'longitude',
            'wake_up_time',
            'bed_time',
            'energy_level',
            'hotel_address',
            'hotel_name',
            'hotel_place_id',
            'hotel_check_in',
            'hotel_check_out',
            'include_breakfast',
            'include_lunch',
            'include_dinner',
            'dietary_notes',
            'mobility_notes',
            'downtime_required',
            'start_date',
            'end_date',
            'trip_purpose',
            'party_adults',
            'party_children',
            'arrival_flight_number',
            'arrival_datetime',
            'arrival_airport',
            'arrival_airline',
            'departure_flight_number',
            'departure_datetime',
            'departure_airport',
            'departure_airline',
            'overall_budget_max',
            'auto_suggest_hotel',
            'num_days',
        ]
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
            'hotel_address': forms.TextInput(attrs={
                'class': 'form-control js-places',
                'placeholder': 'Search for your hotel name or address',
                'data-places': '1',
                'data-types': 'establishment',
                'data-place-id-target': '#id_hotel_place_id',
                'data-name-target': '#id_hotel_name',
                'id': 'hotel_lookup',
            }),
            'hotel_name': forms.HiddenInput(attrs={'id': 'id_hotel_name'}),
            'hotel_place_id': forms.HiddenInput(attrs={'id': 'id_hotel_place_id'}),
            'hotel_check_in': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
                'id': 'hotel_check_in',
            }),
            'hotel_check_out': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
                'id': 'hotel_check_out',
            }),
            'energy_level': forms.Select(attrs={
                'class': 'form-select',
                'id': 'energy_level',
            }),
            'include_breakfast': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'include_breakfast',
                'checked': True,
            }),
            'include_lunch': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'include_lunch',
                'checked': True,
            }),
            'include_dinner': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'include_dinner',
                'checked': True,
            }),
            'dietary_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Dietary preferences, allergies, etc.'
            }),
            'mobility_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Mobility or accessibility considerations'
            }),
            'downtime_required': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'downtime_required'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'id': 'trip_start_date',
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'id': 'trip_end_date',
            }),
            'trip_purpose': forms.Select(attrs={
                'class': 'form-select',
                'id': 'trip_purpose',
            }),
            'party_adults': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'id': 'party_adults',
            }),
            'party_children': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'id': 'party_children',
            }),
            'arrival_datetime': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
                'id': 'arrival_datetime',
            }),
            'arrival_airport': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., JFK',
                'id': 'arrival_airport',
            }),
            'arrival_airline': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Delta Air Lines',
                'id': 'arrival_airline',
            }),
            'arrival_flight_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., DL123',
                'id': 'arrival_flight_number',
            }),
            'departure_datetime': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
                'id': 'departure_datetime',
            }),
            'departure_airport': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., LAX',
                'id': 'departure_airport',
            }),
            'departure_airline': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Southwest',
                'id': 'departure_airline',
            }),
            'departure_flight_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., DL456',
                'id': 'departure_flight_number',
            }),
            'auto_suggest_hotel': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'auto_suggest_hotel',
            }),
            'num_days': forms.HiddenInput(attrs={
                'id': 'num_days',
                'value': 1,
            }),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date must be on or after the start date.")
        return cleaned


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
