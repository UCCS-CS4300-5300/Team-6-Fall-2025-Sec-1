from django.shortcuts import render
from .forms import MoodForm

def mood_questionnaire(request):
    if request.method == 'POST':
        form = MoodForm(request.POST)
        if form.is_valid():
            # process form
            pass
    else:
        form = MoodForm()
    
    return render(request, 'mood_questionnaire.html', {'form': form})
