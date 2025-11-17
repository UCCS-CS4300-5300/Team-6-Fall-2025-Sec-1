'''
Define the imports
'''
from django.shortcuts import render

# --------------------- home views --------------------- #
def index(request):
    ''' Render the homepage '''
    return render(request, "index.html")
