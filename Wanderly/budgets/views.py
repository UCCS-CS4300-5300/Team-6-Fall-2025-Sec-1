import json
import uuid
from pathlib import Path

from django.conf import settings
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
                    saved_items = []
                    for form in formset:
                        if not form.has_changed():
                            continue
                        item = form.save(budget=budget)
                        saved_items.append({
                            "category": item.category,
                            "custom_category": item.custom_category.strip(),
                            "effective_category": item.effective_category,
                            "amount": float(item.amount),
                        })

                if getattr(settings, "CREATE_JSON_OUTPUT", False):
                    export_payload = {
                        "budget_id": budget.id,
                        "user_id": budget.user_id,
                        "created_at": budget.created_at.isoformat(),
                        "items": saved_items,
                    }

                    export_dir = Path(settings.BASE_DIR) / "budgets" / "json"
                    export_dir.mkdir(parents=True, exist_ok=True)
                    export_path = export_dir / f"{uuid.uuid4()}.json"
                    export_path.write_text(json.dumps(export_payload, indent=2))

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
