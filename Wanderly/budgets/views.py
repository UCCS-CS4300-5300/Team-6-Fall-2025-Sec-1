from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render

from .forms import BudgetItemFormSet
from .models import Budget, BudgetItem


@login_required
def itinerary_budget(request):
    if request.method == "POST":
        formset = BudgetItemFormSet(request.POST, prefix="items")

        if formset.is_valid():
            if not any(form.has_changed() for form in formset):
                messages.error(request, "Add at least one budget item before saving.")
            else:
                with transaction.atomic():
                    budget = Budget.objects.create(user=request.user)
                    for form in formset:
                        if not form.has_changed():
                            continue
                        form.save(budget=budget)
                messages.success(request, "Budget saved! You can add more items anytime.")
                return redirect("budgets:itinerary_budget")
        else:
            messages.error(request, "Please fix the highlighted errors and try again.")
    else:
        formset = BudgetItemFormSet(prefix="items")

    context = {
        "formset": formset,
        "budget_other_value": BudgetItem.OTHER,
    }
    return render(request, "budgets/itineraryBudget.html", context)
