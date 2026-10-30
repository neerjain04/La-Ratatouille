
from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),

    # Search feature from main
    path("search/", views.search, name="search"),

    # Display recipe and reviews
    path("recipe/<int:recipe_id>/", views.recipe_detail, name="recipe_detail"),

    # Add a comment
    path("recipe/<int:recipe_id>/add-comment/", views.add_comment, name="add_comment"),

    # Remove a comment
    path("review/<int:review_id>/remove-comment/", views.remove_comment, name="remove_comment"),

    # Edit a comment
    path("review/<int:review_id>/edit-comment/", views.edit_comment, name="edit_comment"),

    
    # Favorite Recipe
    path("recipe/<int:recipe_id>/favorite/", views.favorite_recipe, name="favorite_recipe"),
    
    # Unfavorite Recipe
    path("recipe/<int:recipe_id>/unfavorite/", views.unfavorite_recipe, name="unfavorite_recipe"),


    path("pantry/", views.pantry, name="pantry"),                                 
    path("pantry/delete/", views.pantry_delete, name="pantry_delete"),            
    path("pantry/remove/<int:ingredient_id>/", views.pantry_remove_item, name="pantry_remove_item"),
    path("recipes/<int:recipe_id>/", views.recipe_detail, name="recipe_detail"),   
]
