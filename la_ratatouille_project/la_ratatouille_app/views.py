from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import RatingForm, RecipeForm, RecipeIngredientFormSet, SearchForm
from .models import Favorite, Recipe, Review


def index(request):
    # Show recipes on the home page with their average user rating.
    recipes = Recipe.objects.annotate(average_rating=Avg("reviews__rating")).order_by("-id")
    return render(request, "la_ratatouille_app/home.html", {"recipes": recipes})


def search(request):
    # Match recipes that contain every ingredient selected in the search.
    recipes = Recipe.objects.none()
    form = SearchForm(request.GET or None)
    if form.is_valid() and request.GET:
        where = Q()
        ingredient_ids = form.cleaned_data["ingredients"].values_list("id", flat=True)
        for ingredient_id in ingredient_ids:
            where &= Q(ingredients__id=ingredient_id)
        recipes = Recipe.objects.filter(where).distinct().annotate(
            average_rating=Avg("reviews__rating")
        )

    context = {"recipes": recipes, "form": form}
    return render(request, "la_ratatouille_app/search.html", context)


def recipe_detail(request, pk):
    # Show recipe information and the signed-in user's favorite and rating status.
    recipe = get_object_or_404(
        Recipe.objects.select_related("user").prefetch_related(
            "tags", "recipe_ingredients__ingredient", "recipe_ingredients__unit"
        ),
        pk=pk,
    )
    average_rating = recipe.reviews.aggregate(average=Avg("rating"))["average"]
    user_review = None
    is_favorite = False
    if request.user.is_authenticated:
        user_review = Review.objects.filter(recipe=recipe, user=request.user).first()
        is_favorite = Favorite.objects.filter(recipe=recipe, user=request.user).exists()

    return render(
        request,
        "la_ratatouille_app/recipe_detail.html",
        {
            "recipe": recipe,
            "average_rating": average_rating,
            "user_review": user_review,
            "rating_form": RatingForm(initial={"rating": user_review.rating} if user_review else None),
            "is_favorite": is_favorite,
        },
    )


@login_required
def my_recipes(request):
    # Users can manage the recipes they created from this list.
    recipes = Recipe.objects.filter(user=request.user).annotate(
        average_rating=Avg("reviews__rating")
    )
    return render(
        request,
        "la_ratatouille_app/recipe_list.html",
        {"recipes": recipes, "title": "My recipes"},
    )


@login_required
def favorites(request):
    # Show only recipes this signed-in user has saved.
    recipes = Recipe.objects.filter(favorites__user=request.user).annotate(
        average_rating=Avg("reviews__rating")
    )
    return render(
        request,
        "la_ratatouille_app/recipe_list.html",
        {"recipes": recipes, "title": "Favorite recipes"},
    )


@login_required
def recipe_create(request):
    # Save the recipe and its ingredients together so partial recipes are not kept.
    form = RecipeForm(request.POST or None, request.FILES or None)
    formset = RecipeIngredientFormSet(request.POST or None)
    form_valid = form.is_valid() if request.method == "POST" else False
    formset_valid = formset.is_valid() if request.method == "POST" else False
    if form_valid and formset_valid:
        with transaction.atomic():
            recipe = form.save(commit=False)
            recipe.user = request.user
            recipe.save()
            recipe.tags.set(form.cleaned_data["tags"])
            formset.instance = recipe
            formset.save()
        messages.success(request, "Recipe added.")
        return redirect("recipe_detail", pk=recipe.pk)

    return render(
        request,
        "la_ratatouille_app/recipe_form.html",
        {"form": form, "ingredient_formset": formset, "title": "Add recipe"},
    )


@login_required
def recipe_edit(request, pk):
    # Restrict edits to the recipe's owner.
    recipe = get_object_or_404(Recipe, pk=pk, user=request.user)
    form = RecipeForm(request.POST or None, request.FILES or None, instance=recipe)
    formset = RecipeIngredientFormSet(request.POST or None, instance=recipe)
    form_valid = form.is_valid() if request.method == "POST" else False
    formset_valid = formset.is_valid() if request.method == "POST" else False
    if form_valid and formset_valid:
        with transaction.atomic():
            recipe = form.save()
            recipe.tags.set(form.cleaned_data["tags"])
            formset.save()
        messages.success(request, "Recipe updated.")
        return redirect("recipe_detail", pk=recipe.pk)

    return render(
        request,
        "la_ratatouille_app/recipe_form.html",
        {"form": form, "ingredient_formset": formset, "title": "Edit recipe"},
    )


@login_required
def recipe_delete(request, pk):
    # Show a confirmation page first; only a form submission deletes the recipe.
    recipe = get_object_or_404(Recipe, pk=pk, user=request.user)
    if request.method == "POST":
        recipe.delete()
        messages.success(request, "Recipe deleted.")
        return redirect("my_recipes")
    return render(
        request,
        "la_ratatouille_app/recipe_confirm_delete.html",
        {"recipe": recipe},
    )


@login_required
@require_POST
def rate_recipe(request, pk):
    # Save one rating per user and recipe, replacing that user's earlier rating.
    recipe = get_object_or_404(Recipe, pk=pk)
    form = RatingForm(request.POST)
    if form.is_valid():
        Review.objects.update_or_create(
            recipe=recipe,
            user=request.user,
            defaults={"rating": form.cleaned_data["rating"]},
        )
        messages.success(request, "Your rating was saved.")
    else:
        messages.error(request, "Choose a rating from 1 to 5 stars.")
    return redirect("recipe_detail", pk=recipe.pk)


@login_required
@require_POST
def favorite_recipe(request, pk):
    # Avoid creating duplicate favorites if the action is submitted twice.
    recipe = get_object_or_404(Recipe, pk=pk)
    Favorite.objects.get_or_create(user=request.user, recipe=recipe)
    return redirect("recipe_detail", pk=recipe.pk)


@login_required
@require_POST
def unfavorite_recipe(request, pk):
    # Remove this recipe from the signed-in user's favorites.
    recipe = get_object_or_404(Recipe, pk=pk)
    Favorite.objects.filter(user=request.user, recipe=recipe).delete()
    return redirect("recipe_detail", pk=recipe.pk)
