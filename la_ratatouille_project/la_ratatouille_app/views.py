from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from .pantry import Pantry
from .models import Ingredient, Recipe
from .forms import BatchSizeForm, PantryItemForm, SearchForm
from django.db.models import Q
from functools import reduce

def index(request):
    return HttpResponse("Welcome to La Ratatouille. This page is under construction.")

def search(request):
    recipes = {}
    form = SearchForm(request.GET)
    if len(request.GET) > 0 and form.is_valid():
        # user entered search terms
        where = Q()
        ingredient_ids = (int(id) for id in request.GET.getlist("ingredients"))
        where = reduce(lambda x, y: x & y, (Q(ingredients__id=id) for id in ingredient_ids), where)
        recipes = Recipe.objects.filter(where)

    context = {"recipes": recipes, "form": form} 
    return render(request, "la_ratatouille_app/search.html", context)


# ---------------------------------------------------------------- Pantry (UC 52, 54, 55)
@login_required
def pantry(request):
    """Show the user's pantry and handle the add/edit form (UC 52)."""
    my_pantry = Pantry(request.user)
    form = PantryItemForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        item = my_pantry.add_ingredient(data["ingredient"], data["quantity"], data["unit"])
        if item is None:
            messages.success(request, f"Removed {data['ingredient']}.")
        else:
            messages.success(request, f"Pantry now has {item.quantity} {item.unit or ''} {item.ingredient}.")
        return redirect("pantry")
    return render(request, "la_ratatouille_app/pantry.html", {"items": my_pantry.items(), "form": form})


@login_required
@require_POST
def pantry_remove_item(request, ingredient_id):
    """UC 52 alternate flow: remove one ingredient."""
    ingredient = get_object_or_404(Ingredient, pk=ingredient_id)
    if Pantry(request.user).remove_ingredient(ingredient):
        messages.success(request, f"Removed {ingredient} from your pantry.")
    return redirect("pantry")


@login_required
def pantry_delete(request):
    """UC 55: GET shows a confirmation page, POST empties the pantry."""
    if request.method == "POST":
        count = Pantry(request.user).delete()
        messages.success(request, f"Deleted your pantry ({count} ingredients).")
        return redirect("pantry")
    return render(request, "la_ratatouille_app/pantry_confirm_delete.html")


# ---------------------------------------------------------------- Recipe page (UC 51, 53)
@login_required
def recipe_detail(request, recipe_id):
    """UC 51: ?servings=N rescales the ingredients. UC 53: lists what the pantry is missing."""
    recipe = get_object_or_404(Recipe, pk=recipe_id)
    form = BatchSizeForm(request.GET or None, initial={"servings": recipe.num_servings})
    servings = form.cleaned_data["servings"] if form.is_valid() else recipe.num_servings
    multiplier = recipe.multiplier_for(servings)
    context = {
        "recipe": recipe, "form": form, "servings": servings,
        "lines": recipe.scale_batch(multiplier),
        "missing": recipe.get_missing_ingredients(Pantry(request.user), multiplier),
    }
    return render(request, "la_ratatouille_app/recipe_detail.html", context)
