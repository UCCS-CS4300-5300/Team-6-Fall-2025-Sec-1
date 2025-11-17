"""
This form is used in google routing for the auto complete feature,
it had to be in a form because the html is dynamic and users have
the option to add and remove additional locations.
"""
from django import forms

class AddressForm(forms.Form):
    """Form used to collect location from user with google autocomplete."""
    address = forms.CharField(
        label="Stop",
        widget=forms.TextInput(
            attrs={
                "type": "text",
                "id": "locationSearch",
                "name": "location",
                "class": "form-control js-places",
                "placeholder": "Enter an address...",
                "data-types": "geocode",
                "data-country": "us",
                "data-place-id-target": "#id_place_id",
                "data-lat-target": "#id_lat",
                "data-lng-target": "#id_lng",
                }
            ),
        max_length=255,
    )
