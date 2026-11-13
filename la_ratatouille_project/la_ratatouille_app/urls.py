
from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    # User authentication
    path("signup/", views.signup, name="signup"),
    path("login/", views.user_login, name="login"),
    path("logout/", views.user_logout, name="logout"),

    # Search feature from main
    path("search/", views.search, name="search"),
    path("recipes/new/", views.recipe_create, name="recipe_create"),
    path("recipes/mine/", views.my_recipes, name="my_recipes"),
    path("recipes/favorites/", views.favorite_recipes, name="favorite_recipes"),
    path("recipe/<int:recipe_id>/edit/", views.recipe_edit, name="recipe_edit"),
    path("recipe/<int:recipe_id>/delete/", views.recipe_delete, name="recipe_delete"),
    path("recipe/<int:recipe_id>/rate/", views.rate_recipe, name="rate_recipe"),

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

    # Recipe AI (generate, save)
    path("ai/recipe/", views.ai_generate_recipe, name="ai_generate_recipe"),
    path("ai/recipe/save/", views.ai_save_recipe, name="ai_save_recipe"),
]
