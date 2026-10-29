
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from functools import reduce

from .models import Recipe, Review
from .forms import SearchForm


# Home page
def index(request):
    return HttpResponse("Welcome to La Ratatouille. This page is under construction.")


# Add Comment
@login_required
def add_comment(request, recipe_id):

    if request.method == "POST":

        recipe = get_object_or_404(Recipe, id=recipe_id)

        rating = request.POST.get("rating")
        comment = request.POST.get("comment", "").strip()

        if rating not in ["1", "2", "3", "4", "5"]:
            return HttpResponse("Please select a rating from 1 to 5.", status=400)

        existing_review = Review.objects.filter(
            user=request.user,
            recipe=recipe
        ).exists()

        if existing_review:
            return HttpResponse(
                "You have already reviewed this recipe.",
                status=400
            )

        Review.objects.create(
            user=request.user,
            recipe=recipe,
            rating=int(rating),
            comment=comment
        )

        return redirect("recipe_detail", recipe_id=recipe_id)

    return HttpResponse("Invalid request.", status=405)


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
