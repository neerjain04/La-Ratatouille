from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("search/", views.search, name="search"),
    path("pantry/", views.pantry, name="pantry"),                                   # UC 52
    path("pantry/delete/", views.pantry_delete, name="pantry_delete"),              # UC 55
    path("pantry/remove/<int:ingredient_id>/", views.pantry_remove_item, name="pantry_remove_item"),
    path("recipes/<int:recipe_id>/", views.recipe_detail, name="recipe_detail"),    # UC 51 + 53
]
