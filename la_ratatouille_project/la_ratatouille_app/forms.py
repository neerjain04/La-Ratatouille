from django import forms
from .models import Ingredient, Unit

class SearchForm(forms.Form):
    ingredients = forms.MultipleChoiceField(
        label="Ingredients",
        choices=((i.id, i.name) for i in Ingredient.objects.all()),
        widget=forms.CheckboxSelectMultiple,
        required=False,)

class PantryItemForm(forms.Form):
    """UC 52: add an ingredient or change its amount. Quantity 0 removes it."""
    ingredient = forms.ModelChoiceField(queryset=Ingredient.objects.all())
    quantity = forms.IntegerField(min_value=0)
    unit = forms.ModelChoiceField(queryset=Unit.objects.all(), required=False)


class BatchSizeForm(forms.Form):
    """UC 51: how many servings to make."""
    servings = forms.IntegerField(min_value=1, max_value=500)
