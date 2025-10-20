# Wanderly
Here for all your vacation itinerary needs.

## Setup
### Start virtual environment / install dependencies
```
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```
### Set Environment Variables
Create a `.env` file inside the project root.\
Add the keys from [API Integrations](#api-integrations) to your .env file:
```
GOOGLE_MAPS_BROWSER_KEY=your-browser-key
GOOGLE_ROUTES_SERVER_KEY=your-server-key
```
### Initialize the database
```
python3 manage.py migrate
python3 manage.py createsuperuser # For admin access
```
### Run application locally
```
python3 manage.py runserver 0.0.0.0:3000
```
## Mood Questionnaire

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
```
bash
python manage.py createsuperuser
```
## API Integrations
### Google API Keys
Make sure you have a project in GCP with billing enabled.
#### Enable Necessary APIs
1. In your GCP project head to `APIs & Services -> Enabled APIs & Services`.
2. Click the `+ Enable APIs and services` in blue near the top of the page.
3. Search for the following APIs and enable them if not already done.
   * Routes API
   * Geocoding API
   * Maps JavaScript API
   * Places API (or Places API (New))
   * Maps Static API
4. In the same GCP project head to `APIs and Services -> Credentials`.
5. Create two credentials with the following values:
   1. The second key is used for browser-based requests (e.g., displaying maps).
      * name: browser-maps-key
      * Application Restrictions: None (for testing; use HTTP referrers (websites) in production)
      * API Restrictions: Restrict key
      * Select the following APIs from the dropdown menu:
        * Routes API
        * Geocoding API
        * Places API
      * Click Create
   2. The first key is used for server-side requests (e.g., calculating routes).
      * name: server-routes-key
      * Application Restrictions: None (for testing; use ip-addresses in production)
      * API Restrictions: Restrict key
      * Select the following APIs from the dropdown menu:
        * Maps JavaScript API
        * Places API
        * Places API (New)
        * Maps Static API
      * Click Create
     
