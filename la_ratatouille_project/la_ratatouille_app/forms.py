from django import forms
from .models import Ingredient

class SearchForm(forms.Form):
    ingredients = forms.MultipleChoiceField(
        label="Ingredients",
        choices=((i.id, i.name) for i in Ingredient.objects.all()),
        widget=forms.CheckboxSelectMultiple,
        required=False,)