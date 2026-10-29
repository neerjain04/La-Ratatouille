from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("search/", views.search, name="search"),
    path("recipes/new/", views.recipe_create, name="recipe_create"),
    path("recipes/mine/", views.my_recipes, name="my_recipes"),
    path("recipes/favorites/", views.favorites, name="favorites"),
    path("recipes/<int:pk>/", views.recipe_detail, name="recipe_detail"),
    path("recipes/<int:pk>/edit/", views.recipe_edit, name="recipe_edit"),
    path("recipes/<int:pk>/delete/", views.recipe_delete, name="recipe_delete"),
    path("recipes/<int:pk>/rate/", views.rate_recipe, name="rate_recipe"),
    path("recipes/<int:pk>/favorite/", views.favorite_recipe, name="favorite_recipe"),
    path("recipes/<int:pk>/unfavorite/", views.unfavorite_recipe, name="unfavorite_recipe"),
]
