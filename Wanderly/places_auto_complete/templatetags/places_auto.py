from django import template
from django.conf import settings

register = template.Library()

@register.inclusion_tag("places_auto_complete/js_loader.html", takes_context=True)
def places_js(context):
    return {"GOOGLE_MAPS_BROWSER_KEY": getattr(settings, "GOOGLE_MAPS_BROWSER_KEY", "")}
