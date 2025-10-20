from django import forms

class AddressForm(forms.Form):
    address = forms.CharField(
        label="Stop",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter an address"}),
        max_length=255,
    )