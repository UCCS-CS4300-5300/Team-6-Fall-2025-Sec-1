"""controls all of the form info for the mood questionnaire"""
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
    ('shopping', 'Shopping'),
    ('photography', 'Photography/scenic spots'),
    ('nightlife', 'Nightlife/bars'),
    ('cafes', 'Coffee shops/cafes'),
    ('parks_nature', 'Parks/nature'),
    ('art_galleries', 'Art galleries'),
    ('historical_sites', 'Historical sites'),
    ('live_entertainment', 'Live music/theater'),
    ('fitness_sports', 'Fitness/sports activities'),
    ('wildlife', 'Wildlife/zoos/aquariums'),
    ('beach', 'Beach activities'),
]

class MoodForm(forms.Form):
    """mood form class for questionnaire"""
    destination = forms.CharField(
        label="Where are you traveling to?",
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control js-places',
            'placeholder': 'Enter a city or location...',
            'data-places': '1',
            'data-types': 'geocode',
            'data-country': 'us'
        })
    )

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

