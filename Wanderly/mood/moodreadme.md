# Wanderly Mood Questionnaire

## Overview
The Wanderly Mood Questionnaire collects user preferences to help match their mood and interests to nearby activities using AI.

## Form Features
- **Adventurous Scale**: 1-5 Likert scale measuring how adventurous the user feels
- **Energy Level**: 1-5 Likert scale measuring the user's current energy
- **Interests**: Free-text field for users to describe activities they enjoy

## Accessing the Form
Navigate to: `http://wanderly.social/mood/`

## Database Storage
Form responses are stored in the `MoodResponse` model with the following fields:
- `adventurous` (IntegerField): User's adventurousness rating (1-5)
- `energy` (IntegerField): User's energy level (1-5)
- `what_do_you_enjoy` (TextField): User's interests and preferred activities
- `submitted_at` (DateTimeField): Timestamp of form submission

## Viewing Form Responses - Django admin


1. **Create a superuser:**
```bash
   python manage.py createsuperuser