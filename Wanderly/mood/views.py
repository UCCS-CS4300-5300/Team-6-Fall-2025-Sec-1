from django.shortcuts import render, redirect
from .forms import MoodForm
from .models import MoodResponse

def mood_questionnaire(request):
    if request.method == 'POST':
        form = MoodForm(request.POST)
        if form.is_valid():
            # Save to database
            MoodResponse.objects.create(
                adventurous=form.cleaned_data['adventurous'],
                energy=form.cleaned_data['energy'],
                what_do_you_enjoy=form.cleaned_data['what_do_you_enjoy']
            )
            
            # Redirect using the path instead of name
            return redirect('/mood/')
    else:
        form = MoodForm()
    
    return render(request, 'mood_questionnaire.html', {'form': form})