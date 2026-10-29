from django.shortcuts import render
from django.http import HttpResponse
from .models import Recipe
from .forms import SearchForm
from django.db.models import F, Q, Count, Avg
from functools import reduce

def index(request):
    return HttpResponse("Welcome to La Ratatouille. This page is under construction.")

def search(request):
    '''Handle search requests'''
    form = SearchForm(request.GET)
    recipes = {}
    if len(request.GET) > 0 and form.is_valid():
        # user entered search terms
        ingredients = form.cleaned_data.get("ingredients")
        tags = form.cleaned_data.get("tags")
        min_rating = form.cleaned_data.get("min_rating")
        max_ingredient_count = form.cleaned_data.get("max_ingredient_count")
        max_prep_time = form.cleaned_data.get("max_prep_time")
        recipes = Recipe.objects

        if max_prep_time is not None:
            recipes = recipes.filter(prep_time__lte=max_prep_time) 
        if len(ingredients) > 0:
            recipes = reduce(lambda recipes, ingredient: recipes.filter(ingredients=ingredient),
                             ingredients, recipes)
        if len(tags) > 0:
            recipes = reduce(lambda recipes, tag: recipes.filter(tags=tag),
                            tags, recipes)

        recipes = Recipe.objects.filter(id__in=recipes.values_list("id"))


        # annotate with avg rating and ingredient count
        recipes = recipes.annotate(
            rating=Avg("reviews__rating"),
            ingredient_count=Count("ingredients", distinct=True))
        if min_rating is not None:
            recipes = recipes.filter(rating__gte=min_rating)
        if max_ingredient_count is not None:
            recipes = recipes.filter(ingredient_count__lte=max_ingredient_count)

        # annotate with missing ingredient count for logged in users
        if request.user.is_authenticated:
            # TODO filter by dietary restrictions
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

    context = {"recipes": recipes, "form": form}
    return render(request, "la_ratatouille_app/search.html", context)
