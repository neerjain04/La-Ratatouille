from django import forms
from .models import Ingredient, Tag
from django.core.validators import MinValueValidator, MaxValueValidator

class SearchForm(forms.Form):
    order_by = forms.ChoiceField(
        label="Sort by",
        choices=(("name", "Alphabetical (A->Z)"),
            ("-name", "Alphabetical (Z->A)"),
            ("ingredient_count", "Ingredient count (lowest first)"),
            ("prep_time", "Preparation Time (lowest first)"),
            ("rating", "Rating (lowest first)"),
            ("-rating", "Rating (highest first)"),),
        required=False,
    )

    ingredients = forms.ModelMultipleChoiceField(
        label="Ingredients",
        queryset=Ingredient.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    tags = forms.ModelMultipleChoiceField(
        label="Tag",
        queryset=Tag.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    min_rating = forms.FloatField(
        label="Minimum rating",
        required=False,
        validators=[MinValueValidator(limit_value=1), MaxValueValidator(limit_value=5)],
    )

    max_ingredient_count = forms.IntegerField(
        label="Maximum ingredient count",
        required=False,
        validators=[MinValueValidator(limit_value=1),],
    )

    max_prep_time = forms.IntegerField(
        label="Maximum preparation time",
        required=False,
        validators=[MinValueValidator(limit_value=1),],
    )