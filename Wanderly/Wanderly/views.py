
# Django imports
from django.shortcuts import render

# --------------------- home views --------------------- #
# Homepage
def index(request):
    return render(request, "index.html")
