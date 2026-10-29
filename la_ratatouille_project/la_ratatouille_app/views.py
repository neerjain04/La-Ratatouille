from django.shortcuts import render
from django.http import HttpResponse
from .models import Recipe
from .forms import SearchForm
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
