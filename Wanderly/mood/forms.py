from django import forms

LIKERT = [(i, str(i)) for i in range(1, 6)]

class MoodForm(forms.Form):
    adventurous = forms.ChoiceField(
        label="How adventurous are you feeling?",
        choices=LIKERT, 
        widget=forms.RadioSelect
    )
    energy = forms.ChoiceField(
        label="What is your energy level?",
        choices=LIKERT, 
        widget=forms.RadioSelect
    )

    what_do_you_enjoy = forms.CharField(
        label="What kinds of things do you enjoy doing?",
        required=True,
        widget=forms.Textarea(attrs={
            "rows": 3,
            "class": "form-control",
            "placeholder": "Enter some things you are interested in separated by commas and Wanderly will search for nearby activities"
        })
    )