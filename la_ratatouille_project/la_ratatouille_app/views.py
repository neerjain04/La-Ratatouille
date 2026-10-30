
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from .pantry import Pantry
from .models import Ingredient, Recipe
from .forms import BatchSizeForm, PantryItemForm, SearchForm
from django.db.models import Q
from functools import reduce

from .models import Recipe, Review, Favorite
from .forms import SearchForm, ReviewForm


# Home page
def index(request):
    return HttpResponse("Welcome to La Ratatouille. This page is under construction.")


# Add Comment
@login_required
def add_comment(request, recipe_id):

    if request.method != "POST":
        return HttpResponse("Invalid request.", status=405)

    recipe = get_object_or_404(Recipe, id=recipe_id)
    form = ReviewForm(request.POST)

    if form.is_valid():

        existing_review = Review.objects.filter(
            user=request.user,
            recipe=recipe
        ).first()

        if existing_review:

            if existing_review.comment:
                return HttpResponse(
                    "You have already commented on this recipe.",
                    status=400
                )

            # Add a comment while keeping the existing rating
            existing_review.comment = form.cleaned_data["comment"]
            existing_review.save()

        else:
            review = form.save(commit=False)
            review.user = request.user
            review.recipe = recipe
            review.save()

        return redirect("recipe_detail", recipe_id=recipe_id)

    return HttpResponse("Invalid rating or comment.", status=400)


# Display recipe and reviews
def recipe_detail(request, recipe_id):

    recipe = get_object_or_404(Recipe, id=recipe_id)
    reviews = Review.objects.filter(recipe=recipe)
    form = ReviewForm()

    # Check if the user has favorited this recipe
    is_favorite = False

    if request.user.is_authenticated:
        is_favorite = Favorite.objects.filter(
            user=request.user,
            recipe=recipe
        ).exists()

    return render(request, "la_ratatouille_app/recipe_detail.html", {
        "recipe": recipe,
        "reviews": reviews,
        "form": form,
        "is_favorite": is_favorite
    })


# Remove Comment
@login_required
def remove_comment(request, review_id):

    if request.method != "POST":
        return HttpResponse("Invalid request.", status=405)

    # Find the review belonging to the logged-in user
    review = get_object_or_404(
        Review,
        id=review_id,
        user=request.user
    )

    # Remove only the comment, keeping the rating
    review.comment = ""
    review.save()

    return redirect("recipe_detail", recipe_id=review.recipe.id)


# Search Recipes
def search(request):
    recipes = {}
    form = SearchForm(request.GET)

    if len(request.GET) > 0 and form.is_valid():
        where = Q()
        ingredient_ids = (int(id) for id in request.GET.getlist("ingredients"))
        where = reduce(
            lambda x, y: x & y,
            (Q(ingredients__id=id) for id in ingredient_ids),
            where
        )
        recipes = Recipe.objects.filter(where)

    context = {"recipes": recipes, "form": form}
    return render(request, "la_ratatouille_app/search.html", context)


# Edit Comment
@login_required
def edit_comment(request, review_id):

    # Find the review belonging to the logged-in user
    review = get_object_or_404(
        Review,
        id=review_id,
        user=request.user
    )

    # Only allow editing existing comments
    if not review.comment:
        return HttpResponse("No comment to edit.", status=400)

    if request.method == "POST":

        # Get the updated comment
        new_comment = request.POST.get("comment", "").strip()

        if not new_comment:
            return HttpResponse("Comment cannot be empty.", status=400)

        # Update only the comment
        review.comment = new_comment
        review.save()

        # Return to the recipe page
        return redirect("recipe_detail", recipe_id=review.recipe.id)

    return render(request, "la_ratatouille_app/edit_comment.html", {
        "review": review
    })


# Favorite Recipe
@login_required
def favorite_recipe(request, recipe_id):

    # Only allow form submissions
    if request.method != "POST":
        return HttpResponse("Invalid request.", status=405)

    # Find the recipe
    recipe = get_object_or_404(Recipe, id=recipe_id)

    # Add the recipe to user's favorites
    Favorite.objects.get_or_create(
        user=request.user,
        recipe=recipe
    )

    # Return to the recipe page
    return redirect("recipe_detail", recipe_id=recipe_id)

# Unfavorite Recipe
@login_required
def unfavorite_recipe(request, recipe_id):

    # Only allow form submissions
    if request.method != "POST":
        return HttpResponse("Invalid request.", status=405)

    # Find the recipe
    recipe = get_object_or_404(Recipe, id=recipe_id)

    # Remove the recipe from user's favorites
    Favorite.objects.filter(
        user=request.user,
        recipe=recipe
    ).delete()

    # Return to the recipe page
    return redirect("recipe_detail", recipe_id=recipe_id)


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
