
from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("recipe/<int:recipe_id>/add-comment/", views.add_comment, name="add_comment"),
]
