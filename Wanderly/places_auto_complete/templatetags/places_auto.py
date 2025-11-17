"""
This creates a tag that can be used accross html docs
It imports the script needed for the places auto 
complete functionality. 
You just need to add in the {% load static places_auto %}
tag at the top of the html doc
"""
from django import template
from django.conf import settings

register = template.Library()

# I need to disable unused arg for pylint becuase django needs it for the
# tag injection, but pylint thinks I am not using it b/c its not in the func
@register.inclusion_tag("places_auto_complete/js_loader.html", takes_context=True)
def places_js(context): # pylint: disable=unused-argument
    """
    Template tag that injects the Google Maps Browser API key into the
    places_auto_complete JS loader template so autocomplete functionality
    can be added to any HTML page.
    """
    return {"GOOGLE_MAPS_BROWSER_KEY": getattr(settings, "GOOGLE_MAPS_BROWSER_KEY", "")}
