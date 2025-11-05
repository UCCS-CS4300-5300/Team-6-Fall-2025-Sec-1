from django import forms

from .models import TimePreference


class TimePreferenceForm(forms.ModelForm):
    enable_meals = forms.BooleanField(
        required=False,
        label="Include meal times",
        initial=True,
    )

    class Meta:
        model = TimePreference
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
        # mark meal fields optional
        for field_name in ("wake_up_time", "sleep_time", "breakfast_time", "lunch_time", "dinner_time",
                           "preferred_start_time", "preferred_end_time"):
            self.fields[field_name].required = False

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

    def save(self, user, commit=True):
        instance: TimePreference = super().save(commit=False)
        instance.user = user
        if not self.cleaned_data.get("enable_meals"):
            instance.breakfast_time = None
            instance.lunch_time = None
            instance.dinner_time = None
        if commit:
            instance.save()
        return instance
