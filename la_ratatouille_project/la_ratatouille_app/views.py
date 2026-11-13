from functools import reduce

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from .pantry import Pantry
from .recipe_ai import DRAFT_SESSION_KEY, RecipeAI, save_draft
from .models import Ingredient, Recipe, Review, Favorite
from .forms import (
    AIRecipeForm, BatchSizeForm, PantryItemForm, SearchForm, ReviewForm,
    RatingForm, RecipeForm, RecipeIngredientFormSet,
    SignUpForm
)
from django.db.models import F, Q, Count, Avg
from django.core.paginator import Paginator


# Home page
def index(request):
    return render(request, "la_ratatouille_app/home.html")

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
    '''Handle search requests'''
    form = SearchForm(request.GET)
    context = {"form": form, "recipe_page": None}
    if len(request.GET) > 0 and form.is_valid():
        # user entered search terms
        name = form.cleaned_data.get("name")
        ingredients = form.cleaned_data.get("ingredients")
        tags = form.cleaned_data.get("tags")
        min_rating = form.cleaned_data.get("min_rating")
        max_ingredient_count = form.cleaned_data.get("max_ingredient_count")
        max_prep_time = form.cleaned_data.get("max_prep_time")
        recipes = Recipe.objects

        if name is not None:
            recipes = recipes.filter(name__istartswith=name)
        if max_prep_time is not None:
            recipes = recipes.filter(prep_time__lte=max_prep_time) 
        if len(ingredients) > 0:
            for ingredient in ingredients:
                recipes = recipes.filter(ingredients=ingredient)
        if len(tags) > 0:
            for tag in tags:
                recipes = recipes.filter(tags=tag)

        recipes = Recipe.objects.filter(id__in=recipes.values_list("id"))

        # annotate with avg rating and ingredient count
        recipes = recipes.annotate(
            rating=Avg("reviews__rating"),
            ingredient_count=Count("ingredients", distinct=True))
        if min_rating is not None:
            recipes = recipes.filter(rating__gte=min_rating)
        if max_ingredient_count is not None:
            recipes = recipes.filter(ingredient_count__lte=max_ingredient_count)

        # logged in users
        if request.user.is_authenticated:
            # filter by dietary restrictions
            for restriction in request.user.dietary_restrictions.all():
                recipes = recipes.filter(tags=restriction)

            # annotate with missing ingredient count
            recipes = recipes.annotate(
                count_missing_ingredients=F("ingredient_count") - Count("ingredients", distinct=True,
                                            filter=Q(ingredients__users=request.user)))
  
        sort_criteria = form.cleaned_data.get("order_by")
        # sort by name if no sort order given
        if sort_criteria == "" or sort_criteria is None:
            sort_criteria = "name"
        if sort_criteria in ("name", "-name"):
            recipes = recipes.order_by(sort_criteria)
        else:              
            recipes = recipes.order_by(sort_criteria, "name")

        items_per_page = form.cleaned_data.get("items_per_page", 10)
        paginator = Paginator(recipes, items_per_page)
        page = request.GET.get("page", 1)
        recipe_page = paginator.get_page(page)
        context["recipe_page"] = recipe_page
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


# ---------------------------------------------------------------- Recipe AI
# Edit Recipe Created by AI uses Neer's recipe_edit (the owner sees "Edit recipe" on the recipe page).
@login_required
def ai_generate_recipe(request):
    """Make a recipe from the user's pantry with the recipe AI trained on our dataset."""
    form = AIRecipeForm(request.POST or None)
    draft = None
    if request.method == "POST" and form.is_valid():
        options = form.cleaned_data
        pantry_names = [item.ingredient.name for item in Pantry(request.user).items()] if options["use_pantry"] else []
        main = [options["main_ingredient"].name] if options["main_ingredient"] else []
        draft = RecipeAI.from_file().generate(pantry_names, must_include=main,
                                              servings=options["servings"], size=options["size"])
        request.session[DRAFT_SESSION_KEY] = draft      # kept until the user saves it
    return render(request, "la_ratatouille_app/ai_recipe.html", {"form": form, "draft": draft})


@login_required
@require_POST
def ai_save_recipe(request):
    """Save the recipe the AI just made as one of the user's recipes."""
    draft = request.session.pop(DRAFT_SESSION_KEY, None)
    if draft is None:
        messages.error(request, "Generate a recipe first.")
        return redirect("ai_generate_recipe")
    recipe = save_draft(draft, request.user)
    messages.success(request, f"Saved {recipe.name} to your recipes.")
    return redirect("recipe_detail", recipe_id=recipe.id)

# ---------------------------------------------------------------- Pantry
@login_required
def pantry(request):
    """Show the user's pantry by food group and handle the add/edit form."""
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
    # Same order as the food groups in the menu, then A-Z, so the template can list them under group headings.
    group_order = {code: i for i, code in enumerate(Ingredient.FoodGroup.values)}
    items = sorted(my_pantry.items(), key=lambda item: (group_order.get(item.ingredient.food_group, len(group_order)),
                                                        item.ingredient.name.lower()))
    return render(request, "la_ratatouille_app/pantry.html", {"items": items, "form": form})


@login_required
@require_POST
def pantry_remove_item(request, ingredient_id):
    """alternate flow: remove one ingredient."""
    ingredient = get_object_or_404(Ingredient, pk=ingredient_id)
    if Pantry(request.user).remove_ingredient(ingredient):
        messages.success(request, f"Removed {ingredient} from your pantry.")
    return redirect("pantry")


@login_required
def pantry_delete(request):
    """GET shows a confirmation page, POST empties the pantry."""
    if request.method == "POST":
        count = Pantry(request.user).delete()
        messages.success(request, f"Deleted your pantry ({count} ingredients).")
        return redirect("pantry")
    return render(request, "la_ratatouille_app/pantry_confirm_delete.html")


# ---------------------------------------------------------------- Recipe page 
@login_required
def recipe_detail(request, recipe_id):
    """?servings=N rescales the ingredients. lists what the pantry is missing."""
    recipe = get_object_or_404(Recipe, pk=recipe_id)
    batch_form = BatchSizeForm(request.GET or None, initial={"servings": recipe.num_servings})
    servings = batch_form.cleaned_data["servings"] if batch_form.is_valid() else recipe.num_servings
    multiplier = recipe.multiplier_for(servings)
    user_review = Review.objects.filter(user=request.user, recipe=recipe).first()
    context = {
        "recipe": recipe, "batch_form": batch_form, "servings": servings,
        "lines": recipe.scale_batch(multiplier),
        "missing": recipe.get_missing_ingredients(Pantry(request.user), multiplier),
        "reviews": recipe.reviews.select_related("user"),
        "review_form": ReviewForm(),
        "rating_form": RatingForm(initial={"rating": user_review.rating} if user_review else None),
        "user_review": user_review,
        "average_rating": recipe.reviews.aggregate(average=Avg("rating"))["average"],
        "is_favorite": Favorite.objects.filter(user=request.user, recipe=recipe).exists(),
    }
    return render(request, "la_ratatouille_app/recipe_detail.html", context)

# User Authentication

def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("index")
    else:
        form = SignUpForm()

    return render(request, "la_ratatouille_app/signup.html", {"form": form})


def user_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("index")
        else:
            return render(request, "la_ratatouille_app/login.html", {
                "error": "Invalid username or password."
            })

    return render(request, "la_ratatouille_app/login.html")


@require_POST
def user_logout(request):
    logout(request)
    return redirect("index")
@login_required
def my_recipes(request):
    recipes = Recipe.objects.filter(user=request.user).order_by("name", "id")
    return render(request, "la_ratatouille_app/recipe_list.html", {
        "recipes": recipes, "title": "My recipes",
    })


@login_required
def favorite_recipes(request):
    recipes = Recipe.objects.filter(favorites__user=request.user).order_by("name", "id")
    return render(request, "la_ratatouille_app/recipe_list.html", {
        "recipes": recipes, "title": "Favorite recipes",
    })


@login_required
def recipe_create(request):
    form = RecipeForm(request.POST or None)
    ingredient_formset = RecipeIngredientFormSet(request.POST or None)
    form_valid = form.is_valid() if request.method == "POST" else False
    ingredients_valid = ingredient_formset.is_valid() if request.method == "POST" else False
    if form_valid and ingredients_valid:
        # Save the recipe and ingredient rows together, or not at all.
        with transaction.atomic():
            recipe = form.save(commit=False)
            recipe.user = request.user
            recipe.save()
            recipe.tags.set(form.cleaned_data["tags"])
            ingredient_formset.instance = recipe
            ingredient_formset.save()
        messages.success(request, "Recipe added.")
        return redirect("recipe_detail", recipe_id=recipe.pk)
    return render(request, "la_ratatouille_app/recipe_form.html", {
        "form": form, "ingredient_formset": ingredient_formset, "title": "Add recipe",
    })


@login_required
def recipe_edit(request, recipe_id):
    # A user can only change a recipe that they created.
    recipe = get_object_or_404(Recipe, pk=recipe_id, user=request.user)
    form = RecipeForm(request.POST or None, instance=recipe)
    ingredient_formset = RecipeIngredientFormSet(request.POST or None, instance=recipe)
    form_valid = form.is_valid() if request.method == "POST" else False
    ingredients_valid = ingredient_formset.is_valid() if request.method == "POST" else False
    if form_valid and ingredients_valid:
        with transaction.atomic():
            recipe = form.save()
            recipe.tags.set(form.cleaned_data["tags"])
            ingredient_formset.save()
        messages.success(request, "Recipe updated.")
        return redirect("recipe_detail", recipe_id=recipe.pk)
    return render(request, "la_ratatouille_app/recipe_form.html", {
        "form": form, "ingredient_formset": ingredient_formset, "title": "Edit recipe",
    })


@login_required
def recipe_delete(request, recipe_id):
    recipe = get_object_or_404(Recipe, pk=recipe_id, user=request.user)
    if request.method == "POST":
        recipe.delete()
        messages.success(request, "Recipe deleted.")
        return redirect("my_recipes")
    return render(request, "la_ratatouille_app/recipe_confirm_delete.html", {"recipe": recipe})


@login_required
@require_POST
def rate_recipe(request, recipe_id):
    recipe = get_object_or_404(Recipe, pk=recipe_id)
    form = RatingForm(request.POST)
    if form.is_valid():
        # Ratings share a Review with comments; updating the rating must keep the comment.
        Review.objects.update_or_create(
            user=request.user, recipe=recipe,
            defaults={"rating": form.cleaned_data["rating"]},
        )
        messages.success(request, "Your rating was saved.")
    else:
        messages.error(request, "Choose a rating from 1 to 5 stars.")
    return redirect("recipe_detail", recipe_id=recipe.pk)
def delete_account(request):
    user = request.user
    logout(request)
    user.delete()
    return redirect("index")
