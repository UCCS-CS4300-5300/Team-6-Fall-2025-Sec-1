from django import forms

class AddressForm(forms.Form):
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