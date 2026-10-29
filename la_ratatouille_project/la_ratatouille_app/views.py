

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from functools import reduce

from .models import Recipe, Review
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

    return render(request, "recipe_detail.html", {
        "recipe": recipe,
        "reviews": reviews,
        "form": form
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
