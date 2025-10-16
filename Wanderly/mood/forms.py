from django import forms

LIKERT = [(i, str(i)) for i in range(1, 6)]

INTEREST_CHOICES = [
    ('hiking', 'Hiking'),
    ('water_adventures', 'Water adventures'),
    ('sight_seeing', 'Sight seeing'),
    ('museums', 'Museums'),
    ('try_new_foods', 'Try new foods'),
    ('concert_sporting', 'Attend a concert/sporting event'),
    ('local_market', 'Visit a local market'),
]

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

    what_do_you_enjoy = forms.MultipleChoiceField(
        label="Select from the following some things you are interested in",
        choices=INTEREST_CHOICES,
        required=True,
        widget=forms.CheckboxSelectMultiple
    )